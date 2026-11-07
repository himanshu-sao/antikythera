// Authenticated fetch wrapper (D1).
//
// Token source: a one-time paste stored in sessionStorage under `antikythera_token`
// (chosen over a build-time VITE_API_TOKEN, which would bake the secret into the
// shipped JS bundle). The token lives only for the browser tab session.
//
// apiFetch has the same signature as fetch. With no token stored it calls fetch with
// the exact arguments it received. On a 401 it dispatches the window event
// `antikythera-auth-required` (at most once per AUTH_EVENT_DEBOUNCE_MS) so the
// TokenGate can ask the user for the token.

export const TOKEN_STORAGE_KEY = 'antikythera_token';
export const AUTH_REQUIRED_EVENT = 'antikythera-auth-required';
const AUTH_EVENT_DEBOUNCE_MS = 2000;

let lastAuthEventAt = 0;

function storage(): Storage | null {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null;
  } catch {
    return null;
  }
}

export function getApiToken(): string | null {
  const t = storage()?.getItem(TOKEN_STORAGE_KEY);
  return t ? t : null;
}

export function setApiToken(token: string): void {
  const t = token.trim();
  if (!t) return;
  storage()?.setItem(TOKEN_STORAGE_KEY, t);
  lastAuthEventAt = 0;
}

export function clearApiToken(): void {
  storage()?.removeItem(TOKEN_STORAGE_KEY);
}

function notifyAuthRequired(): void {
  if (typeof window === 'undefined') return;
  const now = Date.now();
  if (now - lastAuthEventAt < AUTH_EVENT_DEBOUNCE_MS) return;
  lastAuthEventAt = now;
  window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
}

/** Test helper: forget the debounce state. */
export function _resetAuthEventDebounce(): void {
  lastAuthEventAt = 0;
}

export async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const token = getApiToken();
  let finalInit = init;
  if (token) {
    const headers = new Headers(init?.headers);
    headers.set('Authorization', `Bearer ${token}`);
    finalInit = { ...init, headers };
  }
  // Resolve fetch at call time so test mocks of globalThis.fetch keep working.
  const res = await fetch(input, finalInit);
  if (res && res.status === 401) notifyAuthRequired();
  return res;
}
