import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import App from '../../App';

const calls: string[] = [];

beforeEach(() => {
  calls.length = 0;
  (globalThis as any).fetch = vi.fn((url: string) => {
    calls.push(String(url));
    const u = String(url);
    const body = u.endsWith('/api/state') ? { items: {}, stages: [] } : [];
    return Promise.resolve({ ok: true, json: async () => body } as any);
  });
  (globalThis as any).localStorage = {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
  } as any;
});

describe('App dead entry points removed (U3)', () => {
  test('never requests /api/boards/virtual on load', async () => {
    render(<App />);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls.some(c => c.includes('/api/boards'))).toBe(false);
  });
});
