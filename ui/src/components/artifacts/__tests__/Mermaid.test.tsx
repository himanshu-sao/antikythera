import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

const { initialize, run } = vi.hoisted(() => ({
  initialize: vi.fn(),
  run: vi.fn(() => Promise.resolve()),
}));

vi.mock('mermaid', () => ({ default: { initialize, run } }));

import { Mermaid } from '../Mermaid';

describe('Mermaid component', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    run.mockClear();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test('initialises mermaid with securityLevel strict and no auto start', () => {
    // initialize runs once at module load; the mock is not cleared between tests.
    expect(initialize).toHaveBeenCalledTimes(1);
    const cfg = initialize.mock.calls[0][0];
    expect(cfg.securityLevel).toBe('strict');
    expect(cfg.startOnLoad).toBe(false);
  });

  test('renders the chart source and asks mermaid to run on its container', async () => {
    render(<Mermaid chart={'graph TD; A-->B'} />);
    expect(screen.getByText('graph TD; A-->B')).toBeInTheDocument();
    expect(run).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(60);
    });
    expect(run).toHaveBeenCalledTimes(1);
    const arg = (run.mock.calls[0] as any)[0];
    expect(arg.nodes).toHaveLength(1);
    expect(arg.nodes[0]).toBe(screen.getByText('graph TD; A-->B'));
  });

  test('does not run after unmount (timer cleared)', async () => {
    const { unmount } = render(<Mermaid chart="graph TD; A-->B" />);
    unmount();
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
    expect(run).not.toHaveBeenCalled();
  });

  test('a rendering failure is logged, not thrown', async () => {
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    run.mockImplementationOnce(() => Promise.reject(new Error('bad diagram')));
    render(<Mermaid chart="not a diagram" />);
    await act(async () => {
      vi.advanceTimersByTime(60);
    });
    expect(err).toHaveBeenCalled();
    err.mockRestore();
  });

  test('code-block mode omits the outer mermaid class', () => {
    const { container } = render(<Mermaid chart="x" isCodeBlock />);
    expect((container.firstChild as HTMLElement).className).not.toMatch(/\bmermaid\b/);
  });
});
