import { renderHook, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import { usePipelineState } from '../usePipelineState';

const STATE = { items: { 'ID-1': { id: 'ID-1', title: 't', stage: 'INTAKE', order: 0, priority: 'low' } } };

function okResponse(body: unknown) {
  return Promise.resolve({ ok: true, json: async () => body } as any);
}

async function flush() {
  // Let resolved fetch promises and their continuations run under fake timers.
  for (let i = 0; i < 5; i++) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock = vi.fn(() => okResponse(STATE));
  (globalThis as any).fetch = fetchMock;
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('usePipelineState polling (U2)', () => {
  test('polls /api/state every 10 seconds while mounted', async () => {
    renderHook(() => usePipelineState());
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      vi.advanceTimersByTime(10000);
    });
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  test('unmount stops the polling interval (no further /api/state calls)', async () => {
    const { unmount } = renderHook(() => usePipelineState());
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    unmount();

    await act(async () => {
      vi.advanceTimersByTime(60000);
    });
    await flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  test('unmount removes the visibilitychange listener so no refetch happens', async () => {
    const { unmount } = renderHook(() => usePipelineState());
    await flush();
    unmount();
    const before = fetchMock.mock.calls.length;

    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    document.dispatchEvent(new Event('visibilitychange'));
    await flush();
    expect(fetchMock.mock.calls.length).toBe(before);
  });

  test('a response arriving after unmount does not update state', async () => {
    let resolveLate: (v: any) => void = () => {};
    fetchMock.mockImplementationOnce(() => new Promise(r => { resolveLate = r; }));
    const { result, unmount } = renderHook(() => usePipelineState());
    const initialState = result.current.state;
    unmount();

    await act(async () => {
      resolveLate({ ok: true, json: async () => STATE });
    });
    await flush();

    expect(result.current.state).toBe(initialState);
    expect(result.current.state.items).toEqual({});
  });

  test('a failure after unmount is not reported as an error', async () => {
    let rejectLate: (e: any) => void = () => {};
    fetchMock.mockImplementationOnce(() => new Promise((_, rej) => { rejectLate = rej; }));
    const { result, unmount } = renderHook(() => usePipelineState());
    unmount();
    await act(async () => {
      rejectLate(new Error('network down'));
    });
    await flush();
    expect(result.current.error).toBeNull();
    expect(console.error).not.toHaveBeenCalled();
  });

  test('while mounted, a successful fetch updates state', async () => {
    const { result } = renderHook(() => usePipelineState());
    await flush();
    expect(result.current.state).toEqual(STATE);
    expect(result.current.loading).toBe(false);
  });
});
