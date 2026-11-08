import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { WorkflowBuilder } from '../WorkflowBuilder';

// P0-4: saving a generated template must POST a template_id. The builder's
// generate response does not always carry one, so the client derives it from
// the name exactly like BlueprintArchitect does (lowercase slug, non-
// alphanumerics to hyphens, trimmed). A server-provided id is kept as-is.

const PROMPT = 'Watch GitHub PR merges and trigger a dev build pipeline';
const PROMPT_INPUT = /GitHub PR merges/i;

const baseTemplate = {
  name: 'Nightly Build Report!',
  description: 'Summarise the nightly build and post it',
  trigger: { type: 'schedule', provider: 'internal', config: { cron: '0 6 * * *' } },
  steps: [
    { id: 1, adapter: 'github', action: 'fetch_resource', config: {}, board_stage: 'EXECUTING' },
  ],
};

type Call = { url: string; init?: RequestInit };

function installFetch(generateBody: any) {
  const calls: Call[] = [];
  (globalThis as any).fetch = vi.fn((url: string, init?: RequestInit) => {
    const u = String(url);
    calls.push({ url: u, init });
    if (u.endsWith('/api/builder/generate')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => generateBody } as any);
    }
    if (u.endsWith('/api/workflows/templates')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) } as any);
    }
    return Promise.reject(new Error(`unexpected fetch ${url}`));
  });
  return calls;
}

async function generateAndSave() {
  fireEvent.change(screen.getByPlaceholderText(PROMPT_INPUT), {
    target: { value: PROMPT },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Generate Blueprint' }));
  await screen.findByText('Blueprint Details');
  fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }));
  await waitFor(() => {
    expect(
      (globalThis as any).fetch.mock.calls.some((c: any[]) => String(c[0]).endsWith('/api/workflows/templates')),
    ).toBe(true);
  });
}

const saveCall = (calls: Call[]) => calls.find((c) => c.url.endsWith('/api/workflows/templates'));

beforeEach(() => {
  sessionStorage.clear();
  (globalThis as any).fetch = vi.fn();
});

describe('WorkflowBuilder save (P0-4)', () => {
  test('derives a template_id from the name when the generated template has none', async () => {
    const calls = installFetch(baseTemplate);
    render(<WorkflowBuilder />);

    await generateAndSave();

    const call = saveCall(calls);
    expect(call).toBeDefined();
    const body = JSON.parse(String(call!.init?.body));
    expect(body.template_id).toBe('nightly-build-report');
    expect(body.name).toBe('Nightly Build Report!');
  });

  test('keeps a server-provided template_id as-is', async () => {
    const calls = installFetch({ ...baseTemplate, template_id: 'srv-42' });
    render(<WorkflowBuilder />);

    await generateAndSave();

    const body = JSON.parse(String(saveCall(calls)!.init?.body));
    expect(body.template_id).toBe('srv-42');
  });

  test('falls back to a stable id when the name slugs to nothing', async () => {
    const calls = installFetch({ ...baseTemplate, name: '!!!' });
    render(<WorkflowBuilder />);

    await generateAndSave();

    const body = JSON.parse(String(saveCall(calls)!.init?.body));
    expect(body.template_id).toBe('workflow');
  });

  test('the edited (not generated) name is what gets slugified', async () => {
    const calls = installFetch(baseTemplate);
    render(<WorkflowBuilder />);

    fireEvent.change(screen.getByPlaceholderText(PROMPT_INPUT), {
      target: { value: PROMPT },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Generate Blueprint' }));
    const nameInput = await screen.findByDisplayValue('Nightly Build Report!');
    fireEvent.change(nameInput, { target: { value: 'Weekly Audit  Sweep' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save to Library' }));

    await waitFor(() => expect(saveCall(calls)).toBeDefined());
    const body = JSON.parse(String(saveCall(calls)!.init?.body));
    expect(body.template_id).toBe('weekly-audit-sweep');
  });
});
