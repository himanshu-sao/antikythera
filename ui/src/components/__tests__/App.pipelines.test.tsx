import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import App from '../../App';
import {
  setApiToken,
  clearApiToken,
  AUTH_REQUIRED_EVENT,
  _resetAuthEventDebounce,
} from '../../api/client';

// P0-2: loadPipelines must go through apiFetch (bearer token, 401 -> TokenGate
// event) instead of a plain fetch that silently renders an empty pipeline list.

type Call = { url: string; init?: RequestInit };

const PIPELINES = [
  { pipeline_id: 'p-1', name: 'Deploy bot', status: 'ACTIVE' },
  { pipeline_id: 'p-2', name: 'Audit sweep', status: 'PAUSED' },
];

function installFetch(pipelinesStatus: number, pipelinesBody?: any) {
  const calls: Call[] = [];
  (globalThis as any).fetch = vi.fn((url: string, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    if (u.endsWith('/api/setup/status')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ complete: true, items: [] }) } as any);
    }
    if (u.endsWith('/api/state')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ items: {}, stages: [] }) } as any);
    }
    if (u.endsWith('/api/pipelines')) {
      return Promise.resolve({
        ok: pipelinesStatus < 400,
        status: pipelinesStatus,
        json: async () => pipelinesBody ?? [],
      } as any);
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => [] } as any);
  });
  return calls;
}

const pipelinesCall = (calls: Call[]) => calls.find((c) => c.url.endsWith('/api/pipelines'));

beforeEach(() => {
  sessionStorage.clear();
  clearApiToken();
  _resetAuthEventDebounce();
});

describe('App loadPipelines (P0-2)', () => {
  test('requests /api/pipelines through apiFetch with the stored bearer token', async () => {
    setApiToken('tok-pipelines');
    const calls = installFetch(200, PIPELINES);
    render(<App />);

    expect(await screen.findByText('Deploy bot')).toBeInTheDocument();
    const call = pipelinesCall(calls);
    expect(call).toBeDefined();
    expect(new Headers(call!.init?.headers).get('Authorization')).toBe('Bearer tok-pipelines');
  });

  test('renders the fetched pipelines as tabs', async () => {
    installFetch(200, PIPELINES);
    render(<App />);
    expect(await screen.findByText('Deploy bot')).toBeInTheDocument();
    expect(screen.getByText('Audit sweep')).toBeInTheDocument();
  });

  test('a 401 fires the auth-required event (TokenGate) instead of a silent empty list', async () => {
    installFetch(401);
    const listener = vi.fn();
    window.addEventListener(AUTH_REQUIRED_EVENT, listener);
    render(<App />);

    await waitFor(() => expect(listener).toHaveBeenCalled());
    window.removeEventListener(AUTH_REQUIRED_EVENT, listener);

    // The gate opens for the user...
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    // ...and no pipeline tab was invented from the failed response.
    expect(screen.queryByText('Deploy bot')).not.toBeInTheDocument();
  });

  test('without a stored token the request still goes out with no Authorization header', async () => {
    const calls = installFetch(200, PIPELINES);
    render(<App />);
    expect(await screen.findByText('Deploy bot')).toBeInTheDocument();
    const call = pipelinesCall(calls);
    expect(new Headers(call!.init?.headers).get('Authorization')).toBeNull();
  });
});
