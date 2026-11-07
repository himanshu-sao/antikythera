import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { useArtifacts } from '../useArtifacts';

// Hook-level D5 contract: submitReview posts the review first, then the forward move only on
// APPROVED. Force sends force: true only through forceMove().

function res(status: number, body: any = {}) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => '',
  } as any);
}

function installFetch(opts: { stage?: string; reviewStatus?: number; moveStatus?: number; moveDetail?: string }) {
  const calls: { url: string; method: string; body?: any }[] = [];
  const fetchMock = vi.fn((url: string, init: any = {}) => {
    const method = (init.method ?? 'GET').toUpperCase();
    calls.push({ url, method, body: init.body ? JSON.parse(init.body) : undefined });
    if (url.endsWith('/review') && method === 'POST') return res(opts.reviewStatus ?? 200, { status: 'success' });
    if (url.endsWith('/api/move')) {
      return res(opts.moveStatus ?? 200, opts.moveStatus === 422 ? { detail: opts.moveDetail ?? 'blocked' } : {});
    }
    if (/\/api\/item\/[^/]+$/.test(url)) return res(200, { id: 'ID-1', stage: opts.stage ?? 'REVIEW_ARCH' });
    return res(404, {});
  });
  (globalThis as any).fetch = fetchMock;
  return calls;
}

async function mountLoaded(onClose = vi.fn()) {
  const hook = renderHook(() => useArtifacts({ itemId: 'ID-1', onClose }));
  await waitFor(() => expect(hook.result.current.itemDetails).not.toBeNull());
  return { ...hook, onClose };
}

describe('useArtifacts.submitReview (D5)', () => {
  beforeEach(() => {
    (window.alert as any).mockClear();
    sessionStorage.clear();
  });

  test('APPROVED: review first, then move to the next stage (REVIEW_ARCH -> TESTING)', async () => {
    const calls = installFetch({ stage: 'REVIEW_ARCH' });
    const { result, onClose } = await mountLoaded();
    act(() => {
      result.current.setReviewStatus('APPROVED');
      result.current.setReviewComments('ok');
    });
    await act(async () => {
      await result.current.submitReview();
    });
    const review = calls.find((c) => c.url.endsWith('/api/item/ID-1/review'));
    expect(review).toMatchObject({ method: 'POST', body: { status: 'APPROVED', comment: 'ok' } });
    const move = calls.find((c) => c.url.endsWith('/api/move'));
    expect(move?.body).toEqual({ item_id: 'ID-1', new_stage: 'TESTING' });
    expect(onClose).toHaveBeenCalled();
  });

  test('APPROVED at REVIEW_TEST moves to APPROVED', async () => {
    const calls = installFetch({ stage: 'REVIEW_TEST' });
    const { result } = await mountLoaded();
    await act(async () => {
      await result.current.submitReview();
    });
    expect(calls.find((c) => c.url.endsWith('/api/move'))?.body.new_stage).toBe('APPROVED');
  });

  test('APPROVED at a stage with no forward step records the review and does not move', async () => {
    const calls = installFetch({ stage: 'DONE' });
    const { result } = await mountLoaded();
    await act(async () => {
      await result.current.submitReview();
    });
    expect(calls.some((c) => c.url.endsWith('/api/item/ID-1/review'))).toBe(true);
    expect(calls.some((c) => c.url.endsWith('/api/move'))).toBe(false);
    expect(window.alert).toHaveBeenCalledWith('Review Approved!');
  });

  test('NEEDS_REVISION: posts the review and never calls /api/move', async () => {
    const calls = installFetch({ stage: 'REVIEW_ARCH' });
    const { result, onClose } = await mountLoaded();
    act(() => {
      result.current.setReviewStatus('NEEDS_REVISION');
      result.current.setReviewComments('rework');
    });
    await act(async () => {
      await result.current.submitReview();
    });
    expect(calls.find((c) => c.url.endsWith('/review'))?.body).toEqual({ status: 'NEEDS_REVISION', comment: 'rework' });
    expect(calls.some((c) => c.url.endsWith('/api/move'))).toBe(false);
    expect(onClose).not.toHaveBeenCalled();
    expect(result.current.gatedMove).toBeNull();
  });

  test('a failed review POST stops before any move', async () => {
    const calls = installFetch({ stage: 'REVIEW_ARCH', reviewStatus: 500 });
    const { result } = await mountLoaded();
    await act(async () => {
      await result.current.submitReview();
    });
    expect(calls.some((c) => c.url.endsWith('/api/move'))).toBe(false);
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Nothing was moved'));
  });

  test('a 422 on the approved move exposes gatedMove and sends no force', async () => {
    const calls = installFetch({ stage: 'REVIEW_ARCH', moveStatus: 422, moveDetail: 'Review gate' });
    const { result, onClose } = await mountLoaded();
    await act(async () => {
      await result.current.submitReview();
    });
    expect(result.current.gatedMove).toEqual({ stage: 'TESTING', reason: 'Review gate' });
    expect(calls.find((c) => c.url.endsWith('/api/move'))!.body).not.toHaveProperty('force');
    expect(onClose).not.toHaveBeenCalled();
  });

  test('forceMove sends force: true for the gated stage and clears gatedMove on success', async () => {
    const calls = installFetch({ stage: 'REVIEW_ARCH', moveStatus: 422, moveDetail: 'Review gate' });
    const { result, onClose } = await mountLoaded();
    await act(async () => {
      await result.current.submitReview();
    });
    // Reconfigure the next move to succeed.
    (globalThis as any).fetch.mockImplementation((url: string, init: any = {}) => {
      calls.push({ url, method: 'POST', body: JSON.parse(init.body) });
      return res(200, {});
    });
    await act(async () => {
      await result.current.forceMove();
    });
    const forced = calls.filter((c) => c.url.endsWith('/api/move')).pop();
    expect(forced!.body).toEqual({ item_id: 'ID-1', new_stage: 'TESTING', force: true });
    expect(result.current.gatedMove).toBeNull();
    expect(onClose).toHaveBeenCalled();
  });

  test('forceMove is a no-op when nothing is gated', async () => {
    const calls = installFetch({ stage: 'REVIEW_ARCH' });
    const { result } = await mountLoaded();
    await act(async () => {
      await result.current.forceMove();
    });
    expect(calls.some((c) => c.url.endsWith('/api/move'))).toBe(false);
  });
});
