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

describe('AutomationStudio (T2a turn-UI shell)', () => {
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
});
