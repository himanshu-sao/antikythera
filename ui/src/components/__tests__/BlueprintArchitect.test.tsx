import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, beforeEach, afterEach } from 'vitest';
import { BlueprintArchitect } from '../BlueprintArchitect';

// Helper: build a fake fetch Response.
const jsonRes = (body: unknown, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
});

const SAMPLE_TEMPLATE = {
  name: 'GitHub PR Release',
  description: 'Triggered on PR merge, runs build and tests.',
  trigger: { type: 'webhook', provider: 'github', config: { event: 'pull_request.closed' } },
  steps: [
    { id: 1, type: 'action', adapter: 'shell', action: 'run_build', config: {}, board_stage: 'EXECUTING' },
    { id: 2, type: 'approval', adapter: 'internal', action: 'human_signoff', config: {}, board_stage: 'APPROVED' },
  ],
};

describe('BlueprintArchitect component', () => {
  const mockedFetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (globalThis as any).fetch = mockedFetch;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('renders prompt textarea and Generate button disabled until prompt >= 10 chars', () => {
    render(<BlueprintArchitect />);
    const generateBtn = screen.getByRole('button', { name: /generate blueprint/i });
    expect(generateBtn).toBeDisabled();

    const textarea = screen.getByLabelText(/workflow description/i);
    fireEvent.change(textarea, { target: { value: 'short' } });
    expect(generateBtn).toBeDisabled();

    fireEvent.change(textarea, { target: { value: 'A long enough description' } });
    expect(generateBtn).not.toBeDisabled();
  });

  test('Generate calls POST /api/builder/generate with prompt and template_name, renders the template', async () => {
    mockedFetch.mockResolvedValueOnce(jsonRes(SAMPLE_TEMPLATE));

    render(<BlueprintArchitect />);
    const textarea = screen.getByLabelText(/workflow description/i);
    fireEvent.change(textarea, { target: { value: 'Create a GitHub PR release workflow that runs build and tests on merge' } });

    const nameInput = screen.getByLabelText(/template name/i);
    fireEvent.change(nameInput, { target: { value: 'Custom Name' } });

    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/builder/generate'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"prompt":"Create a GitHub PR release workflow that runs build and tests on merge"'),
        }),
      );
    });
    // template_name is sent when provided
    expect(mockedFetch.mock.calls[0][1].body).toContain('"template_name":"Custom Name"');

    // Template fields render after generation
    await waitFor(() => {
      expect(screen.getByDisplayValue('GitHub PR Release')).toBeInTheDocument();
      expect(screen.getByText(/Trigger: github/i)).toBeInTheDocument();
      expect(screen.getByText('run_build')).toBeInTheDocument();
    });
  });

  test('Validate calls POST /api/builder/validate and shows success message on valid', async () => {
    mockedFetch.mockResolvedValueOnce(jsonRes(SAMPLE_TEMPLATE)); // generate
    mockedFetch.mockResolvedValueOnce(jsonRes({ status: 'valid', message: 'Template structure is correct' }));

    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), {
      target: { value: 'Create a GitHub PR release workflow that runs build and tests on merge' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));

    await waitFor(() => screen.getByDisplayValue('GitHub PR Release'));

    fireEvent.click(screen.getByRole('button', { name: /^validate$/i }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/builder/validate'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
    await waitFor(() => {
      expect(screen.getByText('Template structure is correct')).toBeInTheDocument();
    });
  });

  test('Validate shows error detail on a 400 response', async () => {
    mockedFetch.mockResolvedValueOnce(jsonRes(SAMPLE_TEMPLATE)); // generate
    mockedFetch.mockResolvedValueOnce(jsonRes({ detail: 'Missing required field: name' }, false, 400));

    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), {
      target: { value: 'Create a GitHub PR release workflow that runs build and tests on merge' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));
    await waitFor(() => screen.getByDisplayValue('GitHub PR Release'));

    fireEvent.click(screen.getByRole('button', { name: /^validate$/i }));

    await waitFor(() => {
      expect(screen.getByText('Missing required field: name')).toBeInTheDocument();
    });
  });

  test('Generate network error shows a toast error and clears the loading state', async () => {
    mockedFetch.mockRejectedValueOnce(new Error('AI generation failed'));

    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), {
      target: { value: 'Create a GitHub PR release workflow that runs build and tests on merge' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));

    // Loading label flips on, then back to idle after rejection.
    await waitFor(() => expect(screen.getByRole('button', { name: /generate blueprint/i })).not.toBeDisabled());
    // No template rendered on error.
    expect(screen.queryByDisplayValue('GitHub PR Release')).not.toBeInTheDocument();
  });

  test('Save is blocked when template contains execution-capable adapter (shell/bob_shell)', async () => {
    const maliciousTemplate = {
      ...SAMPLE_TEMPLATE,
      steps: [
        { id: 1, type: 'action', adapter: 'shell', action: 'run_cmd', config: { script: 'rm -rf /' }, board_stage: 'EXECUTING' },
        { id: 2, type: 'action', adapter: 'github', action: 'create_release', config: {}, board_stage: 'DONE' },
      ],
    };
    mockedFetch.mockResolvedValueOnce(jsonRes(maliciousTemplate));

    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), {
      target: { value: 'Create a GitHub PR release workflow that runs build and tests on merge' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));

    await waitFor(() => screen.getByDisplayValue('GitHub PR Release'));

    // Click Save — should NOT call POST /api/workflows/templates
    fireEvent.click(screen.getByRole('button', { name: /save to library/i }));

    // fetch should have been called only once (generate), not twice (no save call)
    await waitFor(() => expect(mockedFetch).toHaveBeenCalledTimes(1));
    // Save button should return to idle (not stuck in "Saving...")
    await waitFor(() => expect(screen.getByRole('button', { name: /save to library/i })).not.toBeDisabled());
  });

  test('Save succeeds when template contains only safe adapters', async () => {
    const safeTemplate = {
      ...SAMPLE_TEMPLATE,
      steps: [
        { id: 1, type: 'action', adapter: 'github', action: 'create_release', config: {}, board_stage: 'DONE' },
        { id: 2, type: 'action', adapter: 'jira', action: 'update_status', config: {}, board_stage: 'DONE' },
      ],
    };
    mockedFetch.mockResolvedValueOnce(jsonRes(safeTemplate)); // generate
    mockedFetch.mockResolvedValueOnce(jsonRes({ status: 'success', message: 'Template saved' })); // save

    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), {
      target: { value: 'Create a GitHub PR release workflow that runs build and tests on merge' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));

    await waitFor(() => screen.getByDisplayValue('GitHub PR Release'));

    fireEvent.click(screen.getByRole('button', { name: /save to library/i }));

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledTimes(2);
    });
    expect(mockedFetch.mock.calls[1][0]).toContain('/api/workflows/templates');
  });
});
