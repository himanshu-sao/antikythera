import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, beforeEach, afterEach } from 'vitest';
import toast from 'react-hot-toast';
import { BlueprintArchitect, formatApiError } from '../BlueprintArchitect';

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

// S13 / P3-6 (T20): a 422 `detail` is an object or a list, not a string.
describe('formatApiError (S13)', () => {
  test('string detail is returned as is', () => {
    expect(formatApiError('Missing required field: name', 'x')).toBe('Missing required field: name');
  });

  test('{message, violations} renders the message and the violations', () => {
    expect(
      formatApiError({ message: 'Template contains disallowed adapters', violations: ['step 1: adapter shell'] }, 'x'),
    ).toBe('Template contains disallowed adapters: step 1: adapter shell');
  });

  test('{message} alone renders the message', () => {
    expect(formatApiError({ message: 'Template step config validation failed' }, 'x')).toBe(
      'Template step config validation failed',
    );
  });

  test('{violations} alone renders the violations joined', () => {
    expect(formatApiError({ violations: ['a', 'b'] }, 'x')).toBe('a; b');
  });

  test('list of FastAPI validation errors renders loc and msg', () => {
    expect(
      formatApiError([{ loc: ['body', 'prompt'], msg: 'String should have at least 10 characters' }], 'x'),
    ).toBe('prompt: String should have at least 10 characters');
  });

  test('list of plain strings is joined', () => {
    expect(formatApiError(['one', 'two'], 'x')).toBe('one; two');
  });

  test('never produces [object Object]', () => {
    const cases: unknown[] = [{ message: 1 }, { foo: 'bar' }, [{ foo: 1 }], 42, null, undefined];
    for (const c of cases) {
      expect(formatApiError(c, 'fallback')).not.toContain('[object Object]');
    }
  });

  test('falls back when detail is empty or unusable', () => {
    expect(formatApiError(undefined, 'fallback')).toBe('fallback');
    expect(formatApiError(null, 'fallback')).toBe('fallback');
    expect(formatApiError('   ', 'fallback')).toBe('fallback');
    expect(formatApiError({}, 'fallback')).toBe('fallback');
    expect(formatApiError([], 'fallback')).toBe('fallback');
  });
});

describe('BlueprintArchitect 422 errors render readable text (S13)', () => {
  const mockedFetch = vi.fn();
  const PROMPT = 'Create a GitHub PR release workflow that runs build and tests on merge';

  beforeEach(() => {
    vi.clearAllMocks();
    (globalThis as any).fetch = mockedFetch;
  });

  async function generateOk() {
    mockedFetch.mockResolvedValueOnce(jsonRes(SAMPLE_TEMPLATE));
    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), { target: { value: PROMPT } });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));
    await waitFor(() => screen.getByDisplayValue('GitHub PR Release'));
  }

  test('save 422 with {message, violations} shows the violations, not [object Object]', async () => {
    const safeTemplate = {
      ...SAMPLE_TEMPLATE,
      steps: [{ id: 1, type: 'action', adapter: 'github', action: 'create_release', config: {}, board_stage: 'DONE' }],
    };
    mockedFetch.mockResolvedValueOnce(jsonRes(safeTemplate)); // generate
    mockedFetch.mockResolvedValueOnce(
      jsonRes({ detail: { message: 'Template contains disallowed adapters', violations: ["step 1: adapter 'x' not in allowlist"] } }, false, 422),
    );
    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), { target: { value: PROMPT } });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));
    await waitFor(() => screen.getByDisplayValue('GitHub PR Release'));

    const errSpy = vi.spyOn(toast, 'error');
    fireEvent.click(screen.getByRole('button', { name: /save to library/i }));

    await waitFor(() => expect(errSpy).toHaveBeenCalled());
    const message = String(errSpy.mock.calls[0][0]);
    expect(message).toContain('Template contains disallowed adapters');
    expect(message).toContain("not in allowlist");
    expect(message).not.toContain('[object Object]');
    errSpy.mockRestore();
  });

  test('generate 422 with a list of validation errors shows readable text', async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonRes({ detail: [{ loc: ['body', 'prompt'], msg: 'String should have at least 10 characters' }] }, false, 422),
    );
    const errSpy = vi.spyOn(toast, 'error');
    render(<BlueprintArchitect />);
    fireEvent.change(screen.getByLabelText(/workflow description/i), { target: { value: PROMPT } });
    fireEvent.click(screen.getByRole('button', { name: /generate blueprint/i }));

    await waitFor(() => expect(errSpy).toHaveBeenCalled());
    const message = String(errSpy.mock.calls[0][0]);
    expect(message).toContain('String should have at least 10 characters');
    expect(message).not.toContain('[object Object]');
    errSpy.mockRestore();
  });

  test('validate returning 200 status "invalid" shows the violations as invalid', async () => {
    await generateOk();
    mockedFetch.mockResolvedValueOnce(
      jsonRes({
        status: 'invalid',
        message: 'Template failed validation: step 1: adapter shell is an execution-capable adapter',
        violations: ['step 1: adapter shell is an execution-capable adapter'],
      }),
    );
    fireEvent.click(screen.getByRole('button', { name: /^validate$/i }));

    await waitFor(() => {
      expect(screen.getByText(/Template failed validation/)).toBeInTheDocument();
    });
    expect(screen.queryByText('Template structure is correct')).not.toBeInTheDocument();
  });

  test('validate 422 with an object detail shows readable text', async () => {
    await generateOk();
    mockedFetch.mockResolvedValueOnce(
      jsonRes({ detail: { message: 'Steps are invalid', violations: ['step 2: missing action'] } }, false, 422),
    );
    fireEvent.click(screen.getByRole('button', { name: /^validate$/i }));

    await waitFor(() => {
      expect(screen.getByText('Steps are invalid: step 2: missing action')).toBeInTheDocument();
    });
    expect(document.body.textContent).not.toContain('[object Object]');
  });

  test('validate success still shows the valid message', async () => {
    await generateOk();
    mockedFetch.mockResolvedValueOnce(jsonRes({ status: 'valid', message: 'Template structure is correct', violations: [] }));
    fireEvent.click(screen.getByRole('button', { name: /^validate$/i }));
    await waitFor(() => {
      expect(screen.getByText('Template structure is correct')).toBeInTheDocument();
    });
  });
});

