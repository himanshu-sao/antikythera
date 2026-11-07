import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import App from '../../App';

// Setup gate (D9). The status check is a plain fetch; everything else is mocked by URL.
function installFetch(setupStatus: { status: number; body?: any }) {
  const calls: string[] = [];
  (globalThis as any).fetch = vi.fn((url: string) => {
    const u = String(url);
    calls.push(u);
    if (u.endsWith('/api/setup/status')) {
      return Promise.resolve({
        ok: setupStatus.status < 400,
        status: setupStatus.status,
        json: async () => setupStatus.body ?? {},
      } as any);
    }
    const body = u.endsWith('/api/state') ? { items: {}, stages: [] } : [];
    return Promise.resolve({ ok: true, status: 200, json: async () => body } as any);
  });
  return calls;
}

beforeEach(() => {
  (globalThis as any).localStorage = {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
  } as any;
});

describe('App setup gate (D9)', () => {
  test('shows SetupScreen instead of the app when setup is incomplete', async () => {
    installFetch({
      status: 200,
      body: { complete: false, items: [] },
    });
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Set up Antikythera' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Studio$/i })).not.toBeInTheDocument();
  });

  test('shows the app (not SetupScreen) when setup is complete', async () => {
    installFetch({ status: 200, body: { complete: true, items: [] } });
    render(<App />);
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /^Studio$/i }).length).toBeGreaterThan(0),
    );
    expect(screen.queryByRole('heading', { name: 'Set up Antikythera' })).not.toBeInTheDocument();
  });

  test('status check uses plain fetch with no bearer header', async () => {
    const calls = installFetch({ status: 200, body: { complete: true, items: [] } });
    render(<App />);
    await waitFor(() => expect(calls.some((u) => u.endsWith('/api/setup/status'))).toBe(true));
    const statusCall = (globalThis as any).fetch.mock.calls.find((c: any[]) =>
      String(c[0]).endsWith('/api/setup/status'),
    );
    expect(statusCall).toHaveLength(1);
  });

  test('a 403 from status (non-local client) shows the setup screen with the local-only message', async () => {
    installFetch({ status: 403, body: { detail: 'Setup is only available from the local machine' } });
    render(<App />);
    expect(await screen.findByText(/only available from the local machine/)).toBeInTheDocument();
  });

  test('an unreachable backend falls through to the app', async () => {
    (globalThis as any).fetch = vi.fn((url: string) => {
      if (String(url).endsWith('/api/setup/status')) return Promise.reject(new Error('network down'));
      const body = String(url).endsWith('/api/state') ? { items: {}, stages: [] } : [];
      return Promise.resolve({ ok: true, status: 200, json: async () => body } as any);
    });
    render(<App />);
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /^Studio$/i }).length).toBeGreaterThan(0),
    );
  });
});
