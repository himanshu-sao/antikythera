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
});
