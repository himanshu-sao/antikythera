import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from './App';
import type { PipelineState } from './types';

const mockState: PipelineState = {
  items: {
    'ID-001': {
      id: 'ID-001',
      title: 'Test task',
      priority: 'High',
      stage: 'INTAKE',
      confidence_score: 85,
      updated_at: '2026-05-15T00:00:00Z',
    },
  },
};

describe('App Real-time Polling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();

    // Mock visibilityState
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls the state API every 10 seconds', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockState,
    } as Response);

    render(<App />);

    // Flush initial useEffect and its async fetch
    await vi.advanceTimersByTimeAsync(0);

    expect(fetchMock).toHaveBeenCalledWith('http://localhost:8000/api/state');
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Advance time by 10 seconds and resolve async callbacks
    await vi.advanceTimersByTimeAsync(10000);

    expect(fetchMock).toHaveBeenCalledTimes(2);

    // Advance time by another 10 seconds
    await vi.advanceTimersByTimeAsync(10000);

    expect(fetchMock).toHaveBeenCalledTimes(3);
  }, 20000);

  it('stops polling when document is hidden', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockState,
    } as Response);

    render(<App />);

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'hidden',
    });
    document.dispatchEvent(new Event('visibilitychange'));

    await vi.advanceTimersByTimeAsync(20000);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  }, 20000);

  it('resumes polling when document becomes visible again', async () => {
    const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockState,
    } as Response);

    render(<App />);

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'hidden',
    });
    document.dispatchEvent(new Event('visibilitychange'));
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    });
    document.dispatchEvent(new Event('visibilitychange'));

    // The visibilitychange listener calls fetchState immediately when visible
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await vi.advanceTimersByTimeAsync(10000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  }, 20000);
});
