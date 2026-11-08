import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { SetupScreen } from '../SetupScreen';
import { getApiToken, clearApiToken } from '../../api/client';

const SECRET_NAMES = ['NVIDIA_API_KEY', 'JIRA_PAT', 'ANTIKYTHERA_SLACK_WEBHOOK'];

const statusBody = {
  complete: false,
  items: [
    { id: 'env_file', kind: 'env_file', name: '.env', label: 'Environment file', ok: false, state: 'missing', settable: false, secret: false },
    { id: 'NVIDIA_API_KEY', kind: 'provider_key', name: 'NVIDIA_API_KEY', label: 'Provider API key', ok: true, state: 'set', settable: true, secret: true },
    { id: 'GOOGLE_API_KEY', kind: 'provider_key', name: 'GOOGLE_API_KEY', label: 'Provider API key', ok: false, state: 'unset', settable: true, secret: true },
    { id: 'JIRA_BASE_URL', kind: 'jira', name: 'JIRA_BASE_URL', label: 'Jira base URL', ok: false, state: 'unset', settable: true, secret: false },
    { id: 'JIRA_PAT', kind: 'jira', name: 'JIRA_PAT', label: 'Jira personal access token', ok: false, state: 'unset', settable: true, secret: true },
    { id: 'ANTIKYTHERA_SLACK_WEBHOOK', kind: 'slack', name: 'ANTIKYTHERA_SLACK_WEBHOOK', label: 'Slack webhook', ok: false, state: 'unset', settable: true, secret: true },
    { id: 'api_token', kind: 'api_token', name: 'api_token', label: 'API token', ok: false, state: 'missing', settable: false, secret: false },
    { id: 'PORT', kind: 'port', name: 'PORT', label: 'API port', ok: true, state: 'default', settable: true, secret: false },
    { id: 'ANTIKYTHERA_CORS_ORIGINS', kind: 'origins', name: 'ANTIKYTHERA_CORS_ORIGINS', label: 'Allowed UI origins', ok: true, state: 'default', settable: true, secret: false },
    { id: 'data_dir', kind: 'data_dir', name: 'automation-ideas', label: 'Data directory', ok: true, state: 'writable', settable: false, secret: false },
    { id: 'ANTIKYTHERA_BACKUP_DIR', kind: 'backup_dir', name: 'ANTIKYTHERA_BACKUP_DIR', label: 'Backup directory', ok: false, state: 'unset', settable: true, secret: false },
  ],
};

type Call = { url: string; init?: RequestInit };

function installFetch(handlers: Record<string, () => Partial<Response> & { json?: () => Promise<any> }>) {
  const calls: Call[] = [];
  (globalThis as any).fetch = vi.fn((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    const key = Object.keys(handlers).find((k) => String(url).endsWith(k));
    if (!key) return Promise.reject(new Error(`unexpected fetch ${url}`));
    const h = handlers[key]();
    return Promise.resolve({ ok: true, status: 200, json: async () => ({}), ...h } as any);
  });
  return calls;
}

beforeEach(() => {
  clearApiToken();
});

describe('SetupScreen', () => {
  test('renders one section per status group from the mocked status', async () => {
    installFetch({ '/api/setup/status': () => ({ json: async () => statusBody }) });
    render(<SetupScreen />);

    expect(await screen.findByText('AI provider keys')).toBeInTheDocument();
    expect(screen.getByText('Jira')).toBeInTheDocument();
    expect(screen.getByText('Slack notifications')).toBeInTheDocument();
    expect(screen.getByText('API token')).toBeInTheDocument();
    expect(screen.getByText('Ports')).toBeInTheDocument();
    expect(screen.getByText('Allowed origins')).toBeInTheDocument();
    expect(screen.getByText('Data directory')).toBeInTheDocument();
    expect(screen.getByText('Backups')).toBeInTheDocument();
    expect(screen.getByText('Environment file')).toBeInTheDocument();
  });

  test('secret inputs are masked password fields and start empty', async () => {
    installFetch({ '/api/setup/status': () => ({ json: async () => statusBody }) });
    render(<SetupScreen />);
    const nvidia = await screen.findByLabelText(/Provider API key.*NVIDIA_API_KEY/);
    expect(nvidia).toHaveAttribute('type', 'password');
    expect(nvidia).toHaveValue('');
    expect(screen.getByLabelText(/Jira personal access token/)).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText(/Slack webhook/)).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText(/Jira base URL/)).toHaveAttribute('type', 'text');
  });

  test('set-state is shown as presence only and the placeholder never carries a value', async () => {
    installFetch({ '/api/setup/status': () => ({ json: async () => statusBody }) });
    render(<SetupScreen />);
    const nvidia = await screen.findByLabelText(/Provider API key.*NVIDIA_API_KEY/);
    expect(nvidia).toHaveAttribute('placeholder', 'Set. Type a new value to replace it.');
    expect(screen.getAllByText('Set').length).toBeGreaterThan(0);
  });

  test('status values never reach the DOM', async () => {
    const withValue = JSON.parse(JSON.stringify(statusBody));
    (withValue as any).items[1].value = 'sk-should-not-render';
    installFetch({ '/api/setup/status': () => ({ json: async () => withValue }) });
    const { container } = render(<SetupScreen />);
    await screen.findByText('AI provider keys');
    expect(container.innerHTML).not.toContain('sk-should-not-render');
  });

  test('Finish setup sends only typed values to config, then calls complete', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => statusBody }),
      '/api/setup/config': () => ({ json: async () => ({ written: ['JIRA_BASE_URL'], complete: false }) }),
      '/api/setup/complete': () => ({ json: async () => ({ complete: true, api_token: null }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);

    fireEvent.change(await screen.findByLabelText(/Jira base URL/), {
      target: { value: '  https://example.atlassian.net  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));

    await waitFor(() => expect(onComplete).toHaveBeenCalled());

    const configCall = calls.find((c) => c.url.endsWith('/api/setup/config'));
    const completeCall = calls.find((c) => c.url.endsWith('/api/setup/complete'));
    expect(configCall).toBeDefined();
    expect(completeCall).toBeDefined();
    expect(calls.indexOf(configCall!)).toBeLessThan(calls.indexOf(completeCall!));
    expect(configCall!.init?.method).toBe('POST');
    expect(JSON.parse(String(configCall!.init?.body))).toEqual({ JIRA_BASE_URL: 'https://example.atlassian.net' });
    expect(completeCall!.init?.method).toBe('POST');
  });

  test('blank secret fields are not sent', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => statusBody }),
      '/api/setup/config': () => ({ json: async () => ({}) }),
      '/api/setup/complete': () => ({ json: async () => ({ complete: true, api_token: null }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Finish setup' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
    // Nothing typed: config is skipped entirely.
    expect(calls.some((c) => c.url.endsWith('/api/setup/config'))).toBe(false);
  });

  test('a generated token is shown once with a copy button and stored after confirmation', async () => {
    installFetch({
      '/api/setup/status': () => ({ json: async () => statusBody }),
      '/api/setup/complete': () => ({ json: async () => ({ complete: true, api_token: 'tok-ONE-TIME-abc123' }) }),
    });
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(globalThis.navigator, 'clipboard', { value: { writeText }, configurable: true });
    render(<SetupScreen />);

    fireEvent.click(await screen.findByRole('button', { name: 'Finish setup' }));
    expect(await screen.findByTestId('setup-generated-token')).toHaveTextContent('tok-ONE-TIME-abc123');

    fireEvent.click(screen.getByRole('button', { name: 'Copy token' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('tok-ONE-TIME-abc123'));

    const done = screen.getByRole('button', { name: 'I have saved the token' });
    await waitFor(() => expect(done).not.toBeDisabled());
    fireEvent.click(done);
    expect(getApiToken()).toBe('tok-ONE-TIME-abc123');
  });

  test('a 403 from status shows the local-only message instead of the form', async () => {
    installFetch({ '/api/setup/status': () => ({ ok: false, status: 403, json: async () => ({}) }) });
    render(<SetupScreen />);
    expect(await screen.findByRole('alert')).toHaveTextContent('only available from the local machine');
    expect(screen.queryByRole('button', { name: 'Finish setup' })).not.toBeInTheDocument();
  });

  test('a config error shows the server detail and does not finish', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => statusBody }),
      '/api/setup/config': () => ({ ok: false, status: 422, json: async () => ({ detail: 'Unknown setting name' }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);
    fireEvent.change(await screen.findByLabelText(/Jira base URL/), { target: { value: 'https://x.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));
    expect(await screen.findByText('Unknown setting name')).toBeInTheDocument();
    expect(onComplete).not.toHaveBeenCalled();
    expect(calls.some((c) => c.url.endsWith('/api/setup/complete'))).toBe(false);
  });
});

describe('SetupScreen setup secret (P0-1)', () => {
  const secretStatusBody = { ...statusBody, setup_secret_required: true };

  const headerOf = (call: Call | undefined, name: string) =>
    (call?.init?.headers as Record<string, string> | undefined)?.[name];

  test('the setup secret field appears only when status reports it required', async () => {
    installFetch({ '/api/setup/status': () => ({ json: async () => statusBody }) });
    render(<SetupScreen />);
    await screen.findByText('AI provider keys');
    expect(screen.queryByLabelText('Setup secret')).not.toBeInTheDocument();

    installFetch({ '/api/setup/status': () => ({ json: async () => secretStatusBody }) });
    render(<SetupScreen />);
    const field = await screen.findByLabelText('Setup secret');
    expect(field).toHaveAttribute('type', 'password');
    expect(field).toHaveValue('');
    expect(screen.getByText(/setup_secret file under the Antikythera config directory/i)).toBeInTheDocument();
  });

  test('config and complete carry X-Setup-Secret with the typed value', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => secretStatusBody }),
      '/api/setup/config': () => ({ json: async () => ({ written: ['JIRA_BASE_URL'] }) }),
      '/api/setup/complete': () => ({ json: async () => ({ complete: true, api_token: null }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);

    fireEvent.change(await screen.findByLabelText('Setup secret'), { target: { value: '  set-me-123  ' } });
    fireEvent.change(await screen.findByLabelText(/Jira base URL/), { target: { value: 'https://x.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalled());

    const configCall = calls.find((c) => c.url.endsWith('/api/setup/config'));
    const completeCall = calls.find((c) => c.url.endsWith('/api/setup/complete'));
    expect(headerOf(configCall, 'X-Setup-Secret')).toBe('set-me-123');
    expect(headerOf(completeCall, 'X-Setup-Secret')).toBe('set-me-123');
  });

  test('no X-Setup-Secret header is sent when the status does not require one', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => statusBody }),
      '/api/setup/config': () => ({ json: async () => ({}) }),
      '/api/setup/complete': () => ({ json: async () => ({ complete: true, api_token: null }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);
    fireEvent.change(await screen.findByLabelText(/Jira base URL/), { target: { value: 'https://x.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));
    await waitFor(() => expect(onComplete).toHaveBeenCalled());
    expect(headerOf(calls.find((c) => c.url.endsWith('/api/setup/config')), 'X-Setup-Secret')).toBeUndefined();
    expect(headerOf(calls.find((c) => c.url.endsWith('/api/setup/complete')), 'X-Setup-Secret')).toBeUndefined();
  });

  test('a 403 on a wrong secret shows the error and does not lock the screen', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => secretStatusBody }),
      '/api/setup/config': () => ({ ok: false, status: 403, json: async () => ({ detail: 'Forbidden' }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);

    fireEvent.change(await screen.findByLabelText('Setup secret'), { target: { value: 'wrong-secret' } });
    fireEvent.change(await screen.findByLabelText(/Jira base URL/), { target: { value: 'https://x.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/setup secret/i);
    // Not locked: the buttons are still enabled and nothing was completed.
    expect(screen.getByRole('button', { name: 'Finish setup' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save' })).not.toBeDisabled();
    expect(onComplete).not.toHaveBeenCalled();
    expect(calls.some((c) => c.url.endsWith('/api/setup/complete'))).toBe(false);
  });

  test('a 403 from complete (wrong secret at the final step) shows the error and does not finish', async () => {
    const calls = installFetch({
      '/api/setup/status': () => ({ json: async () => secretStatusBody }),
      '/api/setup/config': () => ({ json: async () => ({}) }),
      '/api/setup/complete': () => ({ ok: false, status: 403, json: async () => ({ detail: 'Forbidden' }) }),
    });
    const onComplete = vi.fn();
    render(<SetupScreen onComplete={onComplete} />);

    fireEvent.change(await screen.findByLabelText('Setup secret'), { target: { value: 'wrong-secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish setup' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/setup secret/i);
    expect(screen.getByRole('button', { name: 'Finish setup' })).not.toBeDisabled();
    expect(onComplete).not.toHaveBeenCalled();
    expect(screen.queryByTestId('setup-generated-token')).not.toBeInTheDocument();
  });
});

