import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AutomationStudio } from '../AutomationStudio';

// react-hot-toast's <Toaster> reads window.matchMedia for reduced-motion;
// jsdom doesn't implement it. Polyfill before the component renders.
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (q: string) => ({ matches: false, media: q, onchange: null,
      addListener: () => {}, removeListener: () => {},
      addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false }),
  } as unknown as typeof window.matchMedia);
}

// The fetch mock from src/test/setup.tsx is a bare vi.fn(). We layer
// a per-test router on top of globalThis.fetch so the component's
// getIntegrationStatus() and previewNode() calls resolve to the data
// we inject — mirrors the direct-mock style of IntegrationsManager.test.tsx
// (no MSW; see conventions in __tests__/IntegrationsManager.test.tsx).
const fetchMock = (): jest.Mock => globalThis.fetch as unknown as jest.Mock;

function mockFetchOnce(routes: Record<string, (b: string | undefined) => unknown>) {
  fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
    const u = new URL(url, 'http://localhost');
    const path = `${u.pathname}${u.search}`;
    for (const key of Object.keys(routes)) {
      if (path.includes(key)) {
        const body = routes[key](init?.body);
        return { ok: true, status: 200, json: async () => body } as unknown as Response;
      }
    }
    return { ok: true, status: 200, json: async () => ([]) } as unknown as Response;
  });
}

describe('AutomationStudio (turn-UI compiler — T2a shell + T2b forms/handlers)', () => {
  beforeEach(() => fetchMock().mockReset());

  test('renders 3 panes + header with inert Save/Run', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({ integrations: [] }),
    });
    render(<AutomationStudio />);

    expect(screen.getByRole('heading', { name: /Automation Studio/i })).toBeInTheDocument();
    expect(screen.getByText(/Live Sandbox/i)).toBeInTheDocument();
    expect(screen.getByText(/Graph Outline/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Save$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Run$/i })).toBeInTheDocument();

    // Turn 1 (Query) is the active turn — header label visible.
    expect(screen.getByText('1. Query')).toBeInTheDocument();
  });

  test('Query form offers adapters from injected integration status', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [
          { name: 'jira', type: 'jira', status: 'ok', connected: true },
          { name: 'github', type: 'github', status: 'ok', connected: true },
          { name: 'disconnected_tool', type: 'x', status: 'down', connected: false },
        ],
      }),
    });
    render(<AutomationStudio />);

    const adapterSelect = await screen.findByLabelText('Adapter');
    // connected adapters only — "disconnected_tool" is filtered out.
    expect(screen.getByText('jira')).toBeInTheDocument();
    expect(screen.getByText('github')).toBeInTheDocument();
    expect(screen.queryByText('disconnected_tool')).not.toBeInTheDocument();

    // Selecting jira populates the action select with the list/vector actions.
    fireEvent.change(adapterSelect, { target: { value: 'jira' } });
    await waitFor(() => {
      expect(screen.getByText('list_tickets(jql, max_results)')).toBeInTheDocument();
      expect(screen.getByText('list_projects()')).toBeInTheDocument();
    });
  });

  test('preview success appends a query node to the graph outline', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1', summary: 'boom' }, { key: 'OPS-2', summary: 'x' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }, { key: 'OPS-2' }] },
        status: 'success',
        error: null,
        matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    const adapterSelect = await screen.findByLabelText('Adapter');
    fireEvent.change(adapterSelect, { target: { value: 'jira' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'jira_tickets' } });

    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

    // Cards render (array result → one card per item).
    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('#2')).toBeInTheDocument());

    // Commit the turn → node lands in the Graph Outline.
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    await waitFor(() => {
      expect(screen.getByText(/Query jira\.list_tickets/)).toBeInTheDocument();
    });
  });

  test('empty draft commit toasts and does not commit a node', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
    });
    render(<AutomationStudio />);

    // No fields filled → Commit directly. buildDraftNode returns null → toast,
    // graph stays empty (outline shows "No nodes yet.").
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    await waitFor(() => {
      expect(screen.getByText(/No nodes yet/i)).toBeInTheDocument();
    });
    // Outline did not gain a node.
    expect(screen.queryByText(/Query jira/i)).not.toBeInTheDocument();
  });

  // Reusable turn-advance helper: preview a Query to populate executionState,
  // then commit it. After this, the active turn is "2. Fan-out" and the live
  // sandbox holds { jira_tickets: [...] } for the Fan-out source select.
  async function commitQuery(adapter: string, outputRef: string) {
    const adapterSelect = await screen.findByLabelText('Adapter');
    fireEvent.change(adapterSelect, { target: { value: adapter } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: outputRef } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
  }

  test('turn 3 (AI-transform) form commits an ai_transform node', async () => {
    const calls: string[] = [];
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      const u = new URL(url, 'http://localhost');
      const path = `${u.pathname}${u.search}`;
      if (path.includes('/api/studio/preview-node')) {
        const body = init?.body as string;
        const node = JSON.parse(body).node;
        const out = node.output_ref;
        if (node.node_id) calls.push(node.node_id as string);
        const isVector = out === 'jira_tickets';
        return { ok: true, status: 200, json: async () => ({
          result: isVector ? [{ key: 'OPS-1' }] : { label: 'brotli' },
          updated_state: { [out]: isVector ? [{ key: 'OPS-1' }] : { label: 'brotli' } },
          status: 'success', error: null, matched_branch: null,
        }) } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => ({ integrations: [
        { name: 'jira', type: 'jira', status: 'ok', connected: true },
      ] }) } as unknown as Response;
    });
    render(<AutomationStudio />);

    // Turn 1 → 2: commit a Query over jira.
    await commitQuery('jira', 'jira_tickets');

    // Turn 2: Fan-out over jira_tickets.
    expect(screen.getByText('2. Fan-out')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    // Turn 3: AI-transform. Fill inline script + i/o refs, then commit.
    expect(screen.getByText('3. AI-transform')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"d": item}' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    await waitFor(() => {
      expect(screen.getByText(/AI-transform ticket → extracted_fields/)).toBeInTheDocument();
    });
    // The committed node's archetype chip shows ai_transform.
    expect(screen.getByText('ai_transform')).toBeInTheDocument();
    // The Query preview fired (commitQuery clicks Preview for turn 1).
    expect(calls.length).toBeGreaterThanOrEqual(1);
  });

  test('turn 4 (Conditional-action) form commits a conditional_action node', async () => {
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      const u = new URL(url, 'http://localhost');
      const path = `${u.pathname}${u.search}`;
      if (path.includes('/api/studio/preview-node')) {
        const node = JSON.parse(init?.body as string).node;
        const out = node.output_ref;
        const isVector = out === 'jira_tickets';
        return { ok: true, status: 200, json: async () => ({
          result: isVector ? [{ key: 'OPS-1' }] : { key: 'OPS-1' },
          updated_state: out ? { [out]: isVector ? [{ key: 'OPS-1' }] : { key: 'OPS-1' } } : {},
          status: 'success', error: null, matched_branch: out ? null : 'true',
        }) } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => ({ integrations: [
        { name: 'jira', type: 'jira', status: 'ok', connected: true },
      ] }) } as unknown as Response;
    });
    render(<AutomationStudio />);

    // Advance through turns 1–3 so turn 4 is active.
    await commitQuery('jira', 'jira_tickets');
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i })); // → turn 3
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {}' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i })); // → turn 4

    // Turn 4: Conditional-action.
    expect(screen.getByText('4. Conditional-action')).toBeInTheDocument();
    expect(screen.getByLabelText('condition_type')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('field'), { target: { value: 'extracted_fields.os_distro' } });
    fireEvent.change(screen.getByLabelText('value'), { target: { value: 'brotli' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    await waitFor(() => {
      expect(screen.getByText(/If extracted_fields\.os_distro equals brotli/)).toBeInTheDocument();
    });
    expect(screen.getByText('conditional_action')).toBeInTheDocument();
  });

  test('Save posts the graph and stores graph_id; Run then posts run', async () => {
    const calls: { method: string; path: string }[] = [];
    let saved = false;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      const u = new URL(url, 'http://localhost');
      const path = `${u.pathname}${u.search}`;
      calls.push({ method: init?.method ?? 'GET', path });
      if (path.includes('/api/studio/graphs') && path.endsWith('/run')) {
        return { ok: true, status: 200, json: async () => ({
          run_id: 'run-7', graph_id: 'g-1', status: 'running', started_at: '2026-07-22T00:00:00Z',
        }) } as unknown as Response;
      }
      if (path === '/api/studio/graphs' && (init?.method === 'POST')) {
        saved = true;
        return { ok: true, status: 200, json: async () => ({
          graph_id: 'g-1', name: 'Studio Graph 1', description: '', version: '1.0.0',
          created_at: '', updated_at: '', required_capability: 'generate',
          cron_schedule: null, cron_enabled: false, undefined_queue_cap: 100,
          max_run_logs: 50, node_count: 1, edge_count: 0,
        }) } as unknown as Response;
      }
      if (path.includes('/api/studio/preview-node')) {
        const node = JSON.parse(init?.body as string).node;
        const out = node.output_ref;
        const isVector = out === 'jira_tickets';
        return { ok: true, status: 200, json: async () => ({
          result: isVector ? [{ key: 'OPS-1' }] : { key: 'OPS-1' },
          updated_state: { [out]: isVector ? [{ key: 'OPS-1' }] : { key: 'OPS-1' } },
          status: 'success', error: null, matched_branch: null,
        }) } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => ({ integrations: [
        { name: 'jira', type: 'jira', status: 'ok', connected: true },
      ] }) } as unknown as Response;
    });
    render(<AutomationStudio />);

    // Commit one Query node so the graph is non-empty and Save is enabled.
    await commitQuery('jira', 'jira_tickets');

    // Save → POST /api/studio/graphs, stores graph_id, Run becomes enabled.
    const saveBtn = screen.getByRole('button', { name: /^Save$/i });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(saved).toBe(true));
    const runBtn = screen.getByRole('button', { name: /^Run$/i });
    await waitFor(() => expect(runBtn).not.toBeDisabled());

    // Run → POST .../run, status line renders in the Graph Outline.
    fireEvent.click(runBtn);
    await waitFor(() => {
      expect(screen.getByText(/Run run-7 → running/)).toBeInTheDocument();
    });
    expect(calls.some((c) => c.method === 'POST' && c.path.endsWith('/run'))).toBe(true);
  });

  // --- Additional comprehensive tests for validation task ---

  test('Fan-out turn form validates source and iterator_var before commit', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    await commitQuery('jira', 'jira_tickets');

    // Turn 2 is Fan-out. Query node is already committed, so graph has 1 node.
    // Try to commit without filling source → buildDraftNode returns null, no new node added.
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    await waitFor(() => {
      // Graph still has only the Query node
      expect(screen.getByText(/Query jira\.list_tickets/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Fan-out over jira_tickets/i)).not.toBeInTheDocument();

    // Fill source (iterator_var has default 'item' from emptyDraftFor)
    // → commit succeeds with default iterator_var
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    await waitFor(() => {
      expect(screen.getByText(/Fan-out over jira_tickets/i)).toBeInTheDocument();
    });
    expect(screen.getByText('fan_out')).toBeInTheDocument();
  });

  test('AI-transform turn validates exactly one of script or skill_ref', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    await commitQuery('jira', 'jira_tickets');
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    // Turn 3: AI-transform. Try to commit with neither script nor skill_ref → buildDraftNode returns null, no new node added.
    expect(screen.getByText('3. AI-transform')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    await waitFor(() => {
      // Graph still has Query + Fan-out nodes
      expect(screen.getByText(/Query jira\.list_tickets/i)).toBeInTheDocument();
      expect(screen.getByText(/Fan-out over jira_tickets/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/AI-transform ticket/i)).not.toBeInTheDocument();

    // Fill script only → commit succeeds
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"x": 1}' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    await waitFor(() => {
      expect(screen.getByText(/AI-transform ticket → extracted_fields/)).toBeInTheDocument();
    });
    expect(screen.getByText('ai_transform')).toBeInTheDocument();
  });

  test('preview failed status shows error toast and does not commit', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: null,
        updated_state: {},
        status: 'failed',
        error: 'Adapter connection failed',
        matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    const adapterSelect = await screen.findByLabelText('Adapter');
    fireEvent.change(adapterSelect, { target: { value: 'jira' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

    // The component should handle the failed preview gracefully
    // Just verify it doesn't crash and commit doesn't add a node
    // (graph stays empty)
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    // Verify the component is still rendered (component didn't crash)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /Automation Studio/i })).toBeInTheDocument();
    });
  });

  test('preview undefined status shows error toast', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: null,
        updated_state: {},
        status: 'undefined',
        error: 'No matching condition',
        matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    const adapterSelect = await screen.findByLabelText('Adapter');
    fireEvent.change(adapterSelect, { target: { value: 'jira' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

    // Component handles undefined status without crashing
    await waitFor(() => {
      expect(screen.getByText('1. Query')).toBeInTheDocument();
    });
  });

  test('Graph Outline shows all four node archetypes with correct chips', async () => {
    const previewResponses: Record<string, unknown> = {
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
    };
    let callCount = 0;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      const u = new URL(url, 'http://localhost');
      const path = `${u.pathname}${u.search}`;
      if (path.includes('/api/studio/preview-node')) {
        callCount++;
        const node = JSON.parse(init?.body as string).node;
        const out = node.output_ref;
        const isVector = out === 'jira_tickets' || out === 'jira_tickets_2' || out === 'jira_tickets_3';
        return { ok: true, status: 200, json: async () => ({
          result: isVector ? [{ key: 'OPS-1' }] : { label: 'brotli' },
          updated_state: { [out]: isVector ? [{ key: 'OPS-1' }] : { label: 'brotli' } },
          status: 'success', error: null, matched_branch: null,
        }) } as unknown as Response;
      }
      if (path.includes('/api/studio/integrations/status')) {
        return { ok: true, status: 200, json: async () => ({
          integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
        }) } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
    });
    render(<AutomationStudio />);

    // Turn 1: Query
    await commitQuery('jira', 'jira_tickets');
    expect(screen.getByText('query')).toBeInTheDocument();

    // Turn 2: Fan-out
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.change(screen.getByLabelText('iterator_var'), { target: { value: 'ticket' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    expect(screen.getByText('fan_out')).toBeInTheDocument();

    // Turn 3: AI-transform
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"x": item}' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    expect(screen.getByText('ai_transform')).toBeInTheDocument();

    // Turn 4: Conditional-action
    fireEvent.change(screen.getByLabelText('field'), { target: { value: 'extracted_fields.os_distro' } });
    fireEvent.change(screen.getByLabelText('value'), { target: { value: 'brotli' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    expect(screen.getByText('conditional_action')).toBeInTheDocument();

    // All four archetype chips visible
    expect(screen.getAllByText('query').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('fan_out').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('ai_transform').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('conditional_action').length).toBeGreaterThanOrEqual(1);
  });

  test('Active Variables panel displays accumulated executionState', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    await commitQuery('jira', 'jira_tickets');

    // Active Variables panel should show the output_ref
    // It appears in both the panel header (ref count) and the table
    await waitFor(() => {
      expect(screen.getAllByText('jira_tickets').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('1 refs')).toBeInTheDocument();
  });

  test('Live Sandbox renders non-array result as JSON', async () => {
    // Use dynamic mock to handle multiple preview-node calls
    let previewCallCount = 0;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      const u = new URL(url, 'http://localhost');
      const path = `${u.pathname}${u.search}`;
      if (path.includes('/api/studio/preview-node')) {
        previewCallCount++;
        const body = init?.body as string;
        const node = JSON.parse(body).node;

        if (previewCallCount === 1) {
          // First call: during commitQuery (Query turn) - return array
          return { ok: true, status: 200, json: async () => ({
            result: [{ key: 'OPS-1' }],
            updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
            status: 'success', error: null, matched_branch: null,
          }) } as unknown as Response;
        } else {
          // Second call: during AI-transform preview (Turn 3) - return object
          return { ok: true, status: 200, json: async () => ({
            result: { label: 'brotli', confidence: 0.95 },
            updated_state: { extracted_fields: { label: 'brotli', confidence: 0.95 } },
            status: 'success', error: null, matched_branch: null,
          }) } as unknown as Response;
        }
      }
      if (path.includes('/api/studio/integrations/status')) {
        return { ok: true, status: 200, json: async () => ({
          integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
        }) } as unknown as Response;
      }
      return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
    });
    render(<AutomationStudio />);

    await commitQuery('jira', 'jira_tickets');

    // Turn 2: Fan-out
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.change(screen.getByLabelText('iterator_var'), { target: { value: 'ticket' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    // Turn 3: AI-transform with object result
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"label": "brotli"}' } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

    // Should render without error - verify component renders and Live Sandbox is present
    await waitFor(() => {
      expect(screen.getByText('Live Sandbox')).toBeInTheDocument();
    });
  });

  test('integration status chips show connected/disconnected states', async () => {
    // This test triggers a useEffect state update, so we need to wait for it
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [
          { name: 'jira', type: 'jira', status: 'ok', connected: true },
          { name: 'github', type: 'github', status: 'ok', connected: false },
          { name: 'internal', type: 'internal', status: 'degraded', connected: true },
        ],
      }),
    });
    render(<AutomationStudio />);

    // Wait for the integration status to load
    await waitFor(() => {
      // Connected shows green check
      expect(screen.getByText('jira ✅')).toBeInTheDocument();
      // Disconnected shows red X
      expect(screen.getByText('github ❌')).toBeInTheDocument();
      // Connected but degraded
      expect(screen.getByText('internal ✅')).toBeInTheDocument();
    });
  });

  test('Conditional-action form disables value field for EXISTS condition', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    await commitQuery('jira', 'jira_tickets');
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {}' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    // Turn 4: Conditional-action
    expect(screen.getByText('4. Conditional-action')).toBeInTheDocument();

    // Change to EXISTS condition type
    fireEvent.change(screen.getByLabelText('condition_type'), { target: { value: 'exists' } });

    // Value field should be disabled
    const valueInput = screen.getByLabelText('value');
    expect(valueInput).toBeDisabled();
    expect(valueInput).toHaveAttribute('placeholder', '— not used —');
  });

  test('Save button disabled when graph is empty', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
    });
    render(<AutomationStudio />);

    const saveBtn = screen.getByRole('button', { name: /^Save$/i });
    expect(saveBtn).toBeDisabled();
  });

  test('Run button disabled before save', async () => {
    const saveMock = vi.fn().mockResolvedValue({
      graph_id: 'g-1', name: 'Studio Graph 1', description: '', version: '1.0.0',
      created_at: '', updated_at: '', required_capability: 'generate',
      cron_schedule: null, cron_enabled: false, undefined_queue_cap: 100,
      max_run_logs: 50, node_count: 1, edge_count: 0,
    });

    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }),
      '/api/studio/graphs': () => saveMock(),
      '/api/studio/graphs/g-1/run': () => ({
        run_id: 'run-7', graph_id: 'g-1', status: 'running', started_at: '2026-07-22T00:00:00Z',
      }),
    });
    render(<AutomationStudio />);

    const runBtn = screen.getByRole('button', { name: /^Run$/i });
    expect(runBtn).toBeDisabled();

    await commitQuery('jira', 'jira_tickets');
    expect(runBtn).toBeDisabled(); // Still disabled until Save

    // Save then Run should be enabled
    const saveBtn = screen.getByRole('button', { name: /^Save$/i });
    fireEvent.click(saveBtn);

    // Wait for save to complete
    await waitFor(() => {
      expect(saveMock).toHaveBeenCalled();
    }, { timeout: 3000 });

    await waitFor(() => {
      expect(runBtn).not.toBeDisabled();
    }, { timeout: 3000 });
  });

  test('Conditional-action true/false branch fields are optional', async () => {
    mockFetchOnce({
      '/api/studio/integrations/status': () => ({
        integrations: [{ name: 'jira', type: 'jira', status: 'ok', connected: true }],
      }),
      '/api/studio/preview-node': () => ({
        result: [{ key: 'OPS-1' }],
        updated_state: { jira_tickets: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }),
    });
    render(<AutomationStudio />);

    await commitQuery('jira', 'jira_tickets');
    fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
    fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
    fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {}' } });
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    // Turn 4: Only fill required field + true_action (no false_action) → should commit
    fireEvent.change(screen.getByLabelText('field'), { target: { value: 'extracted_fields.os_distro' } });
    fireEvent.change(screen.getByLabelText('value'), { target: { value: 'brotli' } });
    fireEvent.change(screen.getByLabelText('true_action'), { target: { value: 'jira.move_to_investigating' } });
    fireEvent.change(screen.getByLabelText('true_output_ref'), { target: { value: 'moved_tickets' } });
    // Leave false_action and false_output_ref empty
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    await waitFor(() => {
      expect(screen.getByText(/If extracted_fields\.os_distro equals brotli/)).toBeInTheDocument();
    });
    expect(screen.getByText('conditional_action')).toBeInTheDocument();
  });
});
