import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi } from 'vitest';
import { AutomationStudio, registryKeyFor } from '../AutomationStudio';

// S4/P2: a committed Query node must carry the OperatorRegistry key
// (jira_adapter, github_adapter, internal_adapter), not the integration name.

if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (q: string) => ({ matches: false, media: q, onchange: null,
      addListener: () => {}, removeListener: () => {},
      addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false }),
  } as unknown as typeof window.matchMedia);
}

const INTEGRATIONS = {
  integrations: [
    { name: 'jira_test', type: 'jira', status: 'ok', connected: true },
    { name: 'github_prod', type: 'github', status: 'ok', connected: true },
    { name: 'internal_board', type: 'internal', status: 'ok', connected: true },
  ],
};

function installFetch(captured: Array<{ path: string; body: any }>) {
  const mockFetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
    const u = new URL(url, 'http://localhost');
    const path = `${u.pathname}${u.search}`;
    if (path.includes('/api/studio/integrations/status')) {
      return { ok: true, status: 200, json: async () => INTEGRATIONS } as unknown as Response;
    }
    if (path.includes('/api/studio/preview-node')) {
      const body = JSON.parse(init?.body as string);
      captured.push({ path, body });
      return { ok: true, status: 200, json: async () => ({
        result: [{ key: 'OPS-1' }], updated_state: { out: [{ key: 'OPS-1' }] },
        status: 'success', error: null, matched_branch: null,
      }) } as unknown as Response;
    }
    return { ok: true, status: 200, json: async () => [] } as unknown as Response;
  });
  (globalThis as any).fetch = mockFetch;
  return mockFetch;
}

describe('registryKeyFor', () => {
  test.each([
    ['jira_test', 'jira_adapter'],
    ['JIRA Cloud', 'jira_adapter'],
    ['github_prod', 'github_adapter'],
    ['internal_board', 'internal_adapter'],
  ])('maps %s to %s', (name, key) => {
    expect(registryKeyFor(name)).toBe(key);
  });

  test('returns empty string for an unknown integration', () => {
    expect(registryKeyFor('bob_shell')).toBe('');
    expect(registryKeyFor('something_else')).toBe('');
  });
});

describe('AutomationStudio Query node carries the engine registry key', () => {
  beforeEach(() => {
    (globalThis as any).fetch = undefined;
  });

  test('preview request sends jira_adapter for the jira_test integration', async () => {
    const captured: Array<{ path: string; body: any }> = [];
    installFetch(captured);
    render(<AutomationStudio />);

    const select = await screen.findByLabelText('Adapter');
    fireEvent.change(select, { target: { value: 'jira_test' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'out' } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

    await waitFor(() => expect(captured.length).toBeGreaterThan(0));
    expect(captured[0].body.node.adapter).toBe('jira_adapter');
    expect(captured[0].body.node.adapter).not.toBe('jira_test');
  });

  test('committed node carries the registry key and the outline shows the friendly name', async () => {
    const captured: Array<{ path: string; body: any }> = [];
    installFetch(captured);
    render(<AutomationStudio />);

    const select = await screen.findByLabelText('Adapter');
    fireEvent.change(select, { target: { value: 'github_prod' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'out' } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));
    await waitFor(() => expect(screen.getByText('#1')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Commit turn/i }));

    await waitFor(() => {
      expect(screen.getByText(/Query github_prod\.list_repos/)).toBeInTheDocument();
    });
    // The node the engine would receive uses the registry key.
    expect(captured[0].body.node.adapter).toBe('github_adapter');
  });

  test('internal integration maps to internal_adapter in the preview body', async () => {
    const captured: Array<{ path: string; body: any }> = [];
    installFetch(captured);
    render(<AutomationStudio />);

    const select = await screen.findByLabelText('Adapter');
    fireEvent.change(select, { target: { value: 'internal_board' } });
    fireEvent.change(screen.getByLabelText('output_ref'), { target: { value: 'out' } });
    fireEvent.click(screen.getByRole('button', { name: /Preview/i }));

    await waitFor(() => expect(captured.length).toBeGreaterThan(0));
    expect(captured[0].body.node.adapter).toBe('internal_adapter');
    expect(captured[0].body.node.action).toBe('list_items');
  });
});
