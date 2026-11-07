import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  apiFetch,
  setApiToken,
  clearApiToken,
  getApiToken,
  TOKEN_STORAGE_KEY,
  AUTH_REQUIRED_EVENT,
  _resetAuthEventDebounce,
} from '../client';

const ok = (status = 200) => Promise.resolve({ ok: status < 400, status } as Response);

describe('apiFetch', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    sessionStorage.clear();
    _resetAuthEventDebounce();
    fetchMock = vi.fn(() => ok());
    (globalThis as any).fetch = fetchMock;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('without a token it passes the original arguments through unchanged', async () => {
    await apiFetch('/api/state');
    expect(fetchMock).toHaveBeenCalledWith('/api/state');
    expect(fetchMock.mock.calls[0]).toHaveLength(1);

    const init = { method: 'POST', body: '{}' };
    await apiFetch('/api/items', init);
    expect(fetchMock.mock.calls[1][1]).toBe(init);
  });

  test('adds the bearer header from sessionStorage', async () => {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, 'tok-123');
    await apiFetch('/api/state');
    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer tok-123');
  });

  test('keeps existing headers, method and body when adding the token', async () => {
    setApiToken('tok-abc');
    await apiFetch('/api/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{"a":1}',
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/move');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"a":1}');
    const h = new Headers(init.headers);
    expect(h.get('Content-Type')).toBe('application/json');
    expect(h.get('Authorization')).toBe('Bearer tok-abc');
  });

  test('the stored token overrides a caller-supplied Authorization header', async () => {
    setApiToken('tok-new');
    await apiFetch('/x', { headers: new Headers({ Authorization: 'Bearer stale' }) });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('Authorization')).toBe('Bearer tok-new');
  });

  test('dispatches antikythera-auth-required on a 401 and still returns the response', async () => {
    fetchMock.mockImplementation(() => ok(401));
    const listener = vi.fn();
    window.addEventListener(AUTH_REQUIRED_EVENT, listener);
    const res = await apiFetch('/api/state');
    window.removeEventListener(AUTH_REQUIRED_EVENT, listener);
    expect(res.status).toBe(401);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  test('debounces the event across a burst of 401s', async () => {
    fetchMock.mockImplementation(() => ok(401));
    const listener = vi.fn();
    window.addEventListener(AUTH_REQUIRED_EVENT, listener);
    await Promise.all([apiFetch('/a'), apiFetch('/b'), apiFetch('/c')]);
    window.removeEventListener(AUTH_REQUIRED_EVENT, listener);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  test('fires again after the debounce window', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-07T00:00:00Z'));
    fetchMock.mockImplementation(() => ok(401));
    const listener = vi.fn();
    window.addEventListener(AUTH_REQUIRED_EVENT, listener);
    await apiFetch('/a');
    vi.setSystemTime(new Date('2026-11-07T00:00:05Z'));
    await apiFetch('/b');
    window.removeEventListener(AUTH_REQUIRED_EVENT, listener);
    expect(listener).toHaveBeenCalledTimes(2);
  });

  test('does not fire the event for other error statuses', async () => {
    const listener = vi.fn();
    window.addEventListener(AUTH_REQUIRED_EVENT, listener);
    for (const status of [200, 403, 422, 500]) {
      fetchMock.mockImplementationOnce(() => ok(status));
      await apiFetch('/x');
    }
    window.removeEventListener(AUTH_REQUIRED_EVENT, listener);
    expect(listener).not.toHaveBeenCalled();
  });

  test('propagates network errors', async () => {
    fetchMock.mockImplementation(() => Promise.reject(new Error('offline')));
    await expect(apiFetch('/x')).rejects.toThrow('offline');
  });
});

describe('token helpers', () => {
  beforeEach(() => sessionStorage.clear());

  test('setApiToken stores a trimmed token; clearApiToken removes it', () => {
    setApiToken('  tok-1  ');
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBe('tok-1');
    expect(getApiToken()).toBe('tok-1');
    clearApiToken();
    expect(sessionStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(getApiToken()).toBeNull();
  });

  test('setApiToken ignores a blank token', () => {
    setApiToken('keep');
    setApiToken('   ');
    expect(getApiToken()).toBe('keep');
  });

  test('getApiToken treats an empty stored value as no token', () => {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, '');
    expect(getApiToken()).toBeNull();
  });
});
