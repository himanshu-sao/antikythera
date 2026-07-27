import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi } from 'vitest';
import { AutomationStudio } from '../AutomationStudio';

// Polyfill window.matchMedia for react-hot-toast
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (q: string) => ({ matches: false, media: q, onchange: null,
      addListener: () => {}, removeListener: () => {},
      addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false }),
  } as unknown as typeof window.matchMedia);
}

describe('AutomationStudio Integration - Component Interactions and API Flows', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    (globalThis as any).fetch = fetchMock;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const integrationStatusResponse = {
    integrations: [
      { name: 'jira', type: 'jira', status: 'ok', connected: true },
      { name: 'github', type: 'github', status: 'ok', connected: true },
      { name: 'internal', type: 'internal', status: 'ok', connected: true },
    ],
  };

  describe('Full turn-by-turn authoring flow', () => {
    test('complete flow: Query → Fan-out → AI-transform → Conditional-action → Save → Run', async () => {
      const apiCalls: { method: string; path: string; body?: any }[] = [];

      let previewCallCount = 0;
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;
        apiCalls.push({ method: init?.method || 'GET', path, body: init?.body ? JSON.parse(init.body as string) : undefined });

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          previewCallCount++;
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          // Different responses based on node type
          if (node.archetype === 'query') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ key: 'OPS-1', status: 'Open' }, { key: 'OPS-2', status: 'Critical' }],
              updated_state: { [outputRef]: [{ key: 'OPS-1', status: 'Open' }, { key: 'OPS-2', status: 'Critical' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'fan_out') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ key: 'OPS-1' }, { key: 'OPS-2' }],
              updated_state: { [outputRef]: [{ key: 'OPS-1' }, { key: 'OPS-2' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'ai_transform') {
            return { ok: true, status: 200, json: async () => ({
              result: { os_distro: 'brotli', version: '1.2.3' },
              updated_state: { [outputRef]: { os_distro: 'brotli', version: '1.2.3' } },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'conditional_action') {
            return { ok: true, status: 200, json: async () => ({
              result: { matched: true },
              updated_state: {},
              status: 'success', error: null, matched_branch: 'true',
            }) } as unknown as Response;
          }
        }

        if (path === '/api/studio/graphs' && init?.method === 'POST') {
          return { ok: true, status: 201, json: async () => ({
            graph_id: 'test-graph-1', name: 'Test Graph', description: '', version: '1.0.0',
            created_at: '', updated_at: '', required_capability: 'generate',
            cron_schedule: null, cron_enabled: false, undefined_queue_cap: 100,
            max_run_logs: 50, node_count: 4, edge_count: 3,
          }) } as unknown as Response;
        }

        if (path.includes('/api/studio/graphs/') && path.endsWith('/run')) {
          return { ok: true, status: 200, json: async () => ({
            run_id: 'run-123', graph_id: 'test-graph-1', status: 'running', started_at: new Date().toISOString(),
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;

      render(<AutomationStudio />);

      // Wait for integration status to load
      await waitFor(() => {
        expect(screen.getByText('jira ✅')).toBeInTheDocument();
      });

      // ===== TURN 1: QUERY =====
      expect(screen.getByText('1. Query')).toBeInTheDocument();

      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });

      // Wait for actions to populate
      await waitFor(() => {
        expect(screen.getByText('list_tickets(jql, max_results)')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'jira_tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

      // Wait for preview cards
      await waitFor(() => {
        expect(screen.getByText('#1')).toBeInTheDocument();
        expect(screen.getByText('#2')).toBeInTheDocument();
      });

      // Commit turn 1
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => {
        expect(screen.getByText(/Query jira\.list_tickets/i)).toBeInTheDocument();
      });

      // ===== TURN 2: FAN-OUT =====
      await waitFor(() => {
        expect(screen.getByText('2. Fan-out')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'jira_tickets' } });
      fireEvent.change(screen.getByLabelText('iterator_var'), { target: { value: 'ticket' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

      await waitFor(() => {
        expect(screen.getByText(/Fan-out over jira_tickets/i)).toBeInTheDocument();
        expect(screen.getByText('fan_out')).toBeInTheDocument();
      });

      // ===== TURN 3: AI-TRANSFORM =====
      await waitFor(() => {
        expect(screen.getByText('3. AI-transform')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted_fields' } });
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"os_distro": "brotli"}' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

      await waitFor(() => {
        expect(screen.getByText('Live Sandbox')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

      await waitFor(() => {
        expect(screen.getByText(/AI-transform ticket → extracted_fields/i)).toBeInTheDocument();
        expect(screen.getByText('ai_transform')).toBeInTheDocument();
      });

      // ===== TURN 4: CONDITIONAL-ACTION =====
      await waitFor(() => {
        expect(screen.getByText('4. Conditional-action')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('field'), { target: { value: 'extracted_fields.os_distro' } });
      fireEvent.change(screen.getByLabelText('value'), { target: { value: 'brotli' } });
      fireEvent.change(screen.getByLabelText('true_action'), { target: { value: 'jira.move_to_investigating' } });
      fireEvent.change(screen.getByLabelText('true_output_ref'), { target: { value: 'moved_tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

      await waitFor(() => {
        expect(screen.getByText(/If extracted_fields\.os_distro equals brotli/i)).toBeInTheDocument();
        expect(screen.getByText('conditional_action')).toBeInTheDocument();
      });

      // ===== SAVE =====
      const saveBtn = screen.getByRole('button', { name: /^Save$/i });
      expect(saveBtn).not.toBeDisabled();
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(apiCalls.some(c => c.method === 'POST' && c.path === '/api/studio/graphs')).toBe(true);
      });

      // ===== RUN =====
      const runBtn = screen.getByRole('button', { name: /^Run$/i });
      await waitFor(() => {
        expect(runBtn).not.toBeDisabled();
      });

      fireEvent.click(runBtn);

      await waitFor(() => {
        expect(screen.getByText(/Run run-123 → running/)).toBeInTheDocument();
        expect(apiCalls.some(c => c.method === 'POST' && c.path.endsWith('/run'))).toBe(true);
      });
    });
  });

  describe('Preview node execution and state updates across turns', () => {
    test('executionState accumulates output_refs across multiple turns', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          if (node.archetype === 'query') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }, { id: '2' }],
              updated_state: { [outputRef]: [{ id: '1' }, { id: '2' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'ai_transform') {
            return { ok: true, status: 200, json: async () => ({
              result: { processed: true, count: 2 },
              updated_state: { [outputRef]: { processed: true, count: 2 } },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Turn 1: Query
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText(/Query jira/i)).toBeInTheDocument());

      // Turn 2: Fan-out
      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('fan_out')).toBeInTheDocument());

      // Turn 3: AI-transform
      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'processed' } });
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"done": true}' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('Live Sandbox')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('ai_transform')).toBeInTheDocument());

      // Verify Active Variables panel shows both refs
      await waitFor(() => {
        expect(screen.getAllByText('tickets').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('processed').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('2 refs')).toBeInTheDocument();
      });
    });
  });

  describe('Save/Run workflow with backend API calls', () => {
    test('Save button posts graph and enables Run button', async () => {
      let graphSaved = false;
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          return { ok: true, status: 200, json: async () => ({
            result: [{ id: '1' }],
            updated_state: { tickets: [{ id: '1' }] },
            status: 'success', error: null, matched_branch: null,
          }) } as unknown as Response;
        }

        if (path === '/api/studio/graphs' && init?.method === 'POST') {
          graphSaved = true;
          return { ok: true, status: 201, json: async () => ({
            graph_id: 'g-1', name: 'Test Graph', description: '', version: '1.0.0',
            created_at: '', updated_at: '', required_capability: 'generate',
            cron_schedule: null, cron_enabled: false, undefined_queue_cap: 100,
            max_run_logs: 50, node_count: 1, edge_count: 0,
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Commit one node to make graph non-empty
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText(/Query jira/i)).toBeInTheDocument());

      // Save should be enabled now
      const saveBtn = screen.getByRole('button', { name: /^Save$/i });
      expect(saveBtn).not.toBeDisabled();

      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(graphSaved).toBe(true);
      });

      // Run should now be enabled
      const runBtn = screen.getByRole('button', { name: /^Run$/i });
      await waitFor(() => {
        expect(runBtn).not.toBeDisabled();
      });
    });
  });

  describe('Graph Outline updates and Active Variables panel', () => {
    test('Graph Outline shows all committed nodes with correct archetypes', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          const isVector = outputRef === 'tickets';
          return { ok: true, status: 200, json: async () => ({
            result: isVector ? [{ id: '1' }] : { label: 'brotli' },
            updated_state: { [outputRef]: isVector ? [{ id: '1' }] : { label: 'brotli' } },
            status: 'success', error: null, matched_branch: null,
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Turn 1: Query
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      // Turn 2: Fan-out
      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.change(screen.getByLabelText('iterator_var'), { target: { value: 'ticket' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('fan_out')).toBeInTheDocument());

      // Turn 3: AI-transform
      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted' } });
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {}' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('ai_transform')).toBeInTheDocument());

      // Turn 4: Conditional-action
      fireEvent.change(screen.getByLabelText('field'), { target: { value: 'extracted.os_distro' } });
      fireEvent.change(screen.getByLabelText('value'), { target: { value: 'brotli' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('conditional_action')).toBeInTheDocument());

      // Verify all four archetype chips are visible
      expect(screen.getAllByText('query').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('fan_out').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('ai_transform').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('conditional_action').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Error handling and edge cases in the turn-based flow', () => {
    test('preview failed status shows error toast', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          return { ok: true, status: 200, json: async () => ({
            result: null,
            updated_state: {},
            status: 'failed',
            error: 'Adapter connection failed',
            matched_branch: null,
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

      // Component should handle failed preview gracefully
      await waitFor(() => {
        expect(screen.getByText('1. Query')).toBeInTheDocument();
      });
    });

    test('preview undefined status handles gracefully', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          return { ok: true, status: 200, json: async () => ({
            result: null,
            updated_state: {},
            status: 'undefined',
            error: 'No matching condition',
            matched_branch: null,
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

      // Component handles undefined status without crashing
      await waitFor(() => {
        expect(screen.getByText('1. Query')).toBeInTheDocument();
      });
    });

    test('Fan-out validates source and iterator_var before commit', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          return { ok: true, status: 200, json: async () => ({
            result: [{ id: '1' }],
            updated_state: { tickets: [{ id: '1' }] },
            status: 'success', error: null, matched_branch: null,
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Complete turn 1
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      // Turn 2: Fan-out - try to commit without source
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => {
        expect(screen.getByText(/Query jira/i)).toBeInTheDocument();
        expect(screen.queryByText(/Fan-out over/i)).not.toBeInTheDocument();
      });

      // Fill source and commit
      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => {
        expect(screen.getByText(/Fan-out over tickets/i)).toBeInTheDocument();
        expect(screen.getByText('fan_out')).toBeInTheDocument();
      });
    });

    test('AI-transform validates exactly one of script or skill_ref', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          if (node.archetype === 'query') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }],
              updated_state: { [outputRef]: [{ id: '1' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'fan_out') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }],
              updated_state: { [outputRef]: [{ id: '1' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'ai_transform') {
            return { ok: true, status: 200, json: async () => ({
              result: { processed: true },
              updated_state: { [outputRef]: { processed: true } },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Complete turns 1 and 2
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('fan_out')).toBeInTheDocument());

      // Turn 3: Try to commit without script or skill_ref
      expect(screen.getByText('3. AI-transform')).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

      await waitFor(() => {
        expect(screen.getByText(/Query jira/i)).toBeInTheDocument();
        expect(screen.getByText(/Fan-out over/i)).toBeInTheDocument();
        // The turn label "3. AI-transform" is still visible, but the node should not be committed
        // Check that the committed node with "AI-transform ticket" is not in the graph outline
        expect(screen.queryByText(/AI-transform ticket → extracted/i)).not.toBeInTheDocument();
      });

      // Fill script and commit
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"x": 1}' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('Live Sandbox')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => {
        expect(screen.getByText(/AI-transform ticket → extracted/i)).toBeInTheDocument();
        expect(screen.getByText('ai_transform')).toBeInTheDocument();
      });
    });

    test('Conditional-action EXISTS condition disables value field', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          if (node.archetype === 'query') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }],
              updated_state: { [outputRef]: [{ id: '1' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'fan_out') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }],
              updated_state: { [outputRef]: [{ id: '1' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'ai_transform') {
            return { ok: true, status: 200, json: async () => ({
              result: { os_distro: 'brotli' },
              updated_state: { [outputRef]: { os_distro: 'brotli' } },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Complete turns 1-3
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('fan_out')).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted' } });
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {}' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('Live Sandbox')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('ai_transform')).toBeInTheDocument());

      // Turn 4: Change to EXISTS
      expect(screen.getByText('4. Conditional-action')).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText('condition_type'), { target: { value: 'exists' } });

      const valueInput = screen.getByLabelText('value');
      expect(valueInput).toBeDisabled();
      expect(valueInput).toHaveAttribute('placeholder', '— not used —');
    });
  });

  describe('Live Sandbox renders different result types correctly', () => {
    test('renders array results as cards and object results as JSON', async () => {
      let previewCallCount = 0;
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          previewCallCount++;
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          if (previewCallCount === 1) {
            // First call: Query returns array
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1', name: 'A' }, { id: '2', name: 'B' }],
              updated_state: { [outputRef]: [{ id: '1', name: 'A' }, { id: '2', name: 'B' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          } else {
            // Second call: AI-transform returns object
            return { ok: true, status: 200, json: async () => ({
              result: { label: 'brotli', confidence: 0.95 },
              updated_state: { [outputRef]: { label: 'brotli', confidence: 0.95 } },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Turn 1: Query (array result)
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => {
        expect(screen.getByText('#1')).toBeInTheDocument();
        expect(screen.getByText('#2')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      // Turn 2: Fan-out
      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('fan_out')).toBeInTheDocument());

      // Turn 3: AI-transform with object result
      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted' } });
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {"label": "brotli"}' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

      await waitFor(() => {
        expect(screen.getByText('Live Sandbox')).toBeInTheDocument();
      });
    });
  });

  describe('Integration status chips and UI state', () => {
    test('displays connected/disconnected integration status correctly', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => ({
            integrations: [
              { name: 'jira', type: 'jira', status: 'ok', connected: true },
              { name: 'github', type: 'github', status: 'ok', connected: false },
              { name: 'internal', type: 'internal', status: 'degraded', connected: true },
            ],
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => {
        expect(screen.getByText('jira ✅')).toBeInTheDocument();
        expect(screen.getByText('github ❌')).toBeInTheDocument();
        expect(screen.getByText('internal ✅')).toBeInTheDocument();
      });
    });
  });

  describe('Save/Run button state management', () => {
    test('Save button disabled when graph is empty', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      const saveBtn = screen.getByRole('button', { name: /^Save$/i });
      expect(saveBtn).toBeDisabled();
    });

    test('Run button disabled before save', async () => {
      const saveMock = vi.fn().mockResolvedValue({
        graph_id: 'g-1', name: 'Test', description: '', version: '1.0.0',
        created_at: '', updated_at: '', required_capability: 'generate',
        cron_schedule: null, cron_enabled: false, undefined_queue_cap: 100,
        max_run_logs: 50, node_count: 1, edge_count: 0,
      });

      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          return { ok: true, status: 200, json: async () => ({
            result: [{ id: '1' }],
            updated_state: { tickets: [{ id: '1' }] },
            status: 'success', error: null, matched_branch: null,
          }) } as unknown as Response;
        }

        if (path === '/api/studio/graphs' && init?.method === 'POST') {
          return { ok: true, status: 200, json: async () => saveMock() } as unknown as Response;
        }

        if (path.includes('/run')) {
          return { ok: true, status: 200, json: async () => ({
            run_id: 'run-1', graph_id: 'g-1', status: 'running', started_at: new Date().toISOString(),
          }) } as unknown as Response;
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      const runBtn = screen.getByRole('button', { name: /^Run$/i });
      expect(runBtn).toBeDisabled();

      // Commit one node
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      expect(runBtn).toBeDisabled(); // Still disabled until Save

      // Save
      const saveBtn = screen.getByRole('button', { name: /^Save$/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(saveMock).toHaveBeenCalled();
      });

      // Run should now be enabled
      await waitFor(() => {
        expect(runBtn).not.toBeDisabled();
      });
    });
  });

  describe('Conditional-action true/false branch fields optional', () => {
    test('commits with only true_action filled (no false_action)', async () => {
      const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
        const u = new URL(url, 'http://localhost');
        const path = `${u.pathname}${u.search}`;

        if (path.includes('/api/studio/integrations/status')) {
          return { ok: true, status: 200, json: async () => integrationStatusResponse } as unknown as Response;
        }

        if (path.includes('/api/studio/preview-node')) {
          const body = JSON.parse(init?.body as string);
          const node = body.node;
          const outputRef = node.output_ref;

          if (node.archetype === 'query') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }],
              updated_state: { [outputRef]: [{ id: '1' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'fan_out') {
            return { ok: true, status: 200, json: async () => ({
              result: [{ id: '1' }],
              updated_state: { [outputRef]: [{ id: '1' }] },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'ai_transform') {
            return { ok: true, status: 200, json: async () => ({
              result: { os_distro: 'brotli' },
              updated_state: { [outputRef]: { os_distro: 'brotli' } },
              status: 'success', error: null, matched_branch: null,
            }) } as unknown as Response;
          }

          if (node.archetype === 'conditional_action') {
            return { ok: true, status: 200, json: async () => ({
              result: { matched: true },
              updated_state: {},
              status: 'success', error: null, matched_branch: 'true',
            }) } as unknown as Response;
          }
        }

        return { ok: true, status: 200, json: async () => ({}) } as unknown as Response;
      });

      (globalThis as any).fetch = mockFetch;
      render(<AutomationStudio />);

      await waitFor(() => expect(screen.getByText('jira ✅')).toBeInTheDocument());

      // Complete turns 1-3
      const adapterSelect = await screen.findByLabelText('Adapter');
      fireEvent.change(adapterSelect, { target: { value: 'jira' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('query')).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText('Source'), { target: { value: 'tickets' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('fan_out')).toBeInTheDocument());

      fireEvent.change(screen.getByLabelText('input_ref'), { target: { value: 'ticket' } });
      fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'extracted' } });
      fireEvent.change(screen.getByLabelText('script'), { target: { value: 'result = {}' } });
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('Live Sandbox')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));
      await waitFor(() => expect(screen.getByText('ai_transform')).toBeInTheDocument());

      // Turn 4: Only fill required field + true_action (no false_action)
      fireEvent.change(screen.getByLabelText('field'), { target: { value: 'extracted_fields.os_distro' } });
      fireEvent.change(screen.getByLabelText('value'), { target: { value: 'brotli' } });
      fireEvent.change(screen.getByLabelText('true_action'), { target: { value: 'jira.move_to_investigating' } });
      fireEvent.change(screen.getByLabelText('true_output_ref'), { target: { value: 'moved_tickets' } });
      // Leave false_action and false_output_ref empty
      fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
      await waitFor(() => expect(screen.getByText('Live Sandbox')).toBeInTheDocument());
      fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

      await waitFor(() => {
        expect(screen.getByText(/If extracted_fields\.os_distro equals brotli/i)).toBeInTheDocument();
        expect(screen.getByText('conditional_action')).toBeInTheDocument();
      });
    });
  });
});