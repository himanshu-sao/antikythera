import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import { IntegrationsManager } from '../IntegrationsManager';

const jiraIntegration = {
  name: 'jira-prod',
  type: 'native',
  created_at: '2026-01-01T00:00:00Z',
  status: 'connected',
  config: {
    adapter_module: 'api.adapters.jira',
    jira_url: '*****',
    token: '*****',
  },
};

const mcpIntegration = {
  name: 'github-mcp',
  type: 'mcp',
  created_at: '2026-01-01T00:00:00Z',
  status: 'connected',
  config: {
    url: 'https://mcp.example',
    env: { GITHUB_TOKEN: '*****' },
    enabled: true,
  },
};

interface Call { url: string; init?: RequestInit }

function installFetch(integrations: any[]) {
  const calls: Call[] = [];
  const fn = vi.fn((url: string, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    const body = String(url).endsWith('/api/integrations/') && (!init || !init.method)
      ? integrations
      : { status: 'success' };
    return Promise.resolve({ ok: true, json: async () => body } as any);
  });
  (globalThis as any).fetch = fn;
  return calls;
}

function patchBodies(calls: Call[]) {
  return calls
    .filter(c => c.init?.method === 'PATCH')
    .map(c => JSON.parse(String(c.init!.body)));
}

async function openEdit(name: string) {
  const card = await screen.findByRole('heading', { name });
  const cardRoot = card.closest('.cursor-pointer') as HTMLElement;
  fireEvent.click(within(cardRoot).getByLabelText('Menu'));
  fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
  await screen.findByRole('dialog');
}

beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('IntegrationsManager secrets (P3-3)', () => {
  test('Jira edit: token box is empty (not pre-filled with the masked value)', async () => {
    installFetch([jiraIntegration]);
    render(<IntegrationsManager />);
    await openEdit('jira-prod');
    const tokenBox = screen.getByLabelText('Jira Token Env Var Name') as HTMLInputElement;
    expect(tokenBox.value).toBe('');
    expect(tokenBox.placeholder).toContain('*****');
    const urlBox = screen.getByLabelText('Jira URL Env Var Name') as HTMLInputElement;
    expect(urlBox.value).toBe('');
  });

  test('Jira edit without retyping: saving sends no token and no jira_url', async () => {
    const calls = installFetch([jiraIntegration]);
    render(<IntegrationsManager />);
    await openEdit('jira-prod');

    // Blur the empty token box: must not overwrite the stored secret reference.
    const tokenBox = screen.getByLabelText('Jira Token Env Var Name');
    fireEvent.blur(tokenBox);
    fireEvent.blur(screen.getByLabelText('Jira URL Env Var Name'));

    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(patchBodies(calls)).toHaveLength(1));
    const body = patchBodies(calls)[0];
    expect(body.config).not.toHaveProperty('token');
    expect(body.config).not.toHaveProperty('jira_url');
    expect(body.config.adapter_module).toBe('api.adapters.jira');
    expect(JSON.stringify(body)).not.toContain('${env:');
  });

  test('Jira edit: typing a token reference and blurring sends it', async () => {
    const calls = installFetch([jiraIntegration]);
    render(<IntegrationsManager />);
    await openEdit('jira-prod');

    const tokenBox = screen.getByLabelText('Jira Token Env Var Name');
    fireEvent.change(tokenBox, { target: { value: 'JIRA_PAT_NEW' } });
    fireEvent.blur(tokenBox);

    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(patchBodies(calls)).toHaveLength(1));
    expect(patchBodies(calls)[0].config.token).toBe('${env:JIRA_PAT_NEW}');
  });

  test('Jira edit: typing a Jira URL env name and blurring sends it', async () => {
    const calls = installFetch([jiraIntegration]);
    render(<IntegrationsManager />);
    await openEdit('jira-prod');

    const urlBox = screen.getByLabelText('Jira URL Env Var Name');
    fireEvent.change(urlBox, { target: { value: 'JIRA_BASE_URL' } });
    fireEvent.blur(urlBox);

    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(patchBodies(calls)).toHaveLength(1));
    const body = patchBodies(calls)[0];
    expect(body.config.jira_url).toBe('${env:JIRA_BASE_URL}');
    expect(body.config).not.toHaveProperty('token');
  });

  test('Config JSON edit: masked token is not re-sent unless the user types a new value', async () => {
    const calls = installFetch([mcpIntegration]);
    render(<IntegrationsManager />);
    await openEdit('github-mcp');

    const textarea = screen.getByRole('dialog').querySelector('textarea') as HTMLTextAreaElement;
    // The textarea shows the masked env value, never a stored secret.
    expect(textarea.value).toContain('"GITHUB_TOKEN": "*****"');
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(patchBodies(calls)).toHaveLength(1));
    const body = patchBodies(calls)[0];
    expect(body.config.env).toEqual({});
    expect(JSON.stringify(body)).not.toContain('*****');
  });

  test('Config JSON edit: a newly typed env value is sent', async () => {
    const calls = installFetch([mcpIntegration]);
    render(<IntegrationsManager />);
    await openEdit('github-mcp');

    const textarea = screen.getByRole('dialog').querySelector('textarea') as HTMLTextAreaElement;
    const edited = textarea.value.replace('"GITHUB_TOKEN": "*****"', '"GITHUB_TOKEN": "ghp_new_value"');
    fireEvent.change(textarea, { target: { value: edited } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(patchBodies(calls)).toHaveLength(1));
    expect(patchBodies(calls)[0].config.env).toEqual({ GITHUB_TOKEN: 'ghp_new_value' });
  });

  test('the textarea keeps what the user typed (no re-masking on each render)', async () => {
    installFetch([mcpIntegration]);
    render(<IntegrationsManager />);
    await openEdit('github-mcp');
    const textarea = screen.getByRole('dialog').querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '{"token": "typed-now"}' } });
    expect(textarea.value).toBe('{"token": "typed-now"}');
  });
});

describe('IntegrationsManager dead Secret Vault removed (U3)', () => {
  test('there is no Manage Secrets button and no Secret Vault dialog', async () => {
    installFetch([jiraIntegration]);
    render(<IntegrationsManager />);
    await screen.findByRole('heading', { name: 'jira-prod' });
    expect(screen.queryByRole('button', { name: /Manage Secrets/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Secret Vault/i)).not.toBeInTheDocument();
  });

  test('the manager never requests the /api/integrations/secrets routes', async () => {
    const calls = installFetch([jiraIntegration]);
    render(<IntegrationsManager />);
    await screen.findByRole('heading', { name: 'jira-prod' });
    await openEdit('jira-prod');
    expect(calls.some(c => c.url.includes('/secrets'))).toBe(false);
  });

  test('Add Connection still works', async () => {
    installFetch([]);
    render(<IntegrationsManager />);
    fireEvent.click(screen.getByRole('button', { name: /\+ Add Connection/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Add Integration')).toBeInTheDocument();
  });
});
