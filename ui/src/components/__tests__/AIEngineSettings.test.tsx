import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import AIEngineSettings from '../AIEngineSettings';

const CONFIG = {
  default_provider: 'google_gemma',
  default_model_id: 'gemma-7b',
  models: [
    {
      model_id: 'gemma-7b',
      name: 'Gemma 7B',
      provider: 'google_gemma',
      is_default: true,
      api_key_set: true,
      endpoint: null,
      context_window: 4096,
      temperature: 0.7,
      max_tokens: 2048,
    },
    {
      model_id: 'llama3.1',
      name: 'Llama 3.1',
      provider: 'ollama',
      is_default: false,
      api_key_set: false,
      endpoint: null,
      context_window: 8192,
      temperature: 0.7,
      max_tokens: 2048,
    },
  ],
  connection_settings: { timeout_seconds: 30, max_retries: 3, enable_fallback: true, enable_caching: false },
};

function jsonResponse(body: unknown, init: { ok?: boolean; headers?: Record<string, string> } = {}) {
  const headers = init.headers ?? {};
  return {
    ok: init.ok ?? true,
    json: async () => body,
    text: async () => JSON.stringify(body),
    headers: { get: (k: string) => headers[k.toLowerCase()] ?? null },
  } as any;
}

let fetchMock: ReturnType<typeof vi.fn>;

function installFetch(logsResponse?: () => any) {
  fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.startsWith('/api/ai-engine/logs')) {
      return Promise.resolve(logsResponse ? logsResponse() : jsonResponse({ logs: '' }));
    }
    if (u === '/api/ai-engine/config') return Promise.resolve(jsonResponse(CONFIG));
    return Promise.resolve(jsonResponse({ success: true }));
  });
  (globalThis as any).fetch = fetchMock;
}

async function openTab(name: RegExp) {
  await screen.findByText(/AI Engine Configuration/i);
  fireEvent.click(screen.getByRole('button', { name }));
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AIEngineSettings component', () => {
  test('renders loading state initially', () => {
    installFetch();
    render(<AIEngineSettings />);
    expect(screen.getByText(/Loading AI Engine configuration.../i)).toBeInTheDocument();
  });
});

describe('AIEngineSettings logs tab (P3-1)', () => {
  test('requests lines=2000 (not the old tail byte count) and renders the JSON logs field', async () => {
    installFetch(() => jsonResponse({ logs: 'line one\nline two' }));
    render(<AIEngineSettings />);
    await openTab(/^Logs$/);

    const pre = await screen.findByText(/line one/);
    expect(pre.textContent).toBe('line one\nline two');
    // Not the raw JSON envelope.
    expect(screen.queryByText(/"logs"/)).not.toBeInTheDocument();

    const logCall = fetchMock.mock.calls.map((c) => String(c[0])).find((u) => u.startsWith('/api/ai-engine/logs'));
    expect(logCall).toBe('/api/ai-engine/logs?lines=2000');
    expect(logCall).not.toContain('tail=');
  });

  test('shows the truncated notice when X-Log-Truncated is true', async () => {
    installFetch(() => jsonResponse({ logs: 'abc' }, { headers: { 'x-log-truncated': 'true' } }));
    render(<AIEngineSettings />);
    await openTab(/^Logs$/);
    expect(await screen.findByTestId('logs-truncated')).toBeInTheDocument();
  });

  test('has no truncated notice when the header is absent', async () => {
    installFetch(() => jsonResponse({ logs: 'abc' }));
    render(<AIEngineSettings />);
    await openTab(/^Logs$/);
    await screen.findByText('abc');
    expect(screen.queryByTestId('logs-truncated')).not.toBeInTheDocument();
  });

  test('tolerates a response without the logs field', async () => {
    installFetch(() => jsonResponse({}));
    render(<AIEngineSettings />);
    await openTab(/^Logs$/);
    await waitFor(() => expect(screen.queryByText(/Loading\.\.\./)).not.toBeInTheDocument());
    expect(screen.queryByText('undefined')).not.toBeInTheDocument();
  });

  test('shows an error message when the request fails', async () => {
    installFetch(() => jsonResponse({}, { ok: false }));
    render(<AIEngineSettings />);
    await openTab(/^Logs$/);
    expect(await screen.findByText('Error loading logs')).toBeInTheDocument();
    expect(screen.queryByTestId('logs-truncated')).not.toBeInTheDocument();
  });
});
