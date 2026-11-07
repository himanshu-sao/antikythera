import React, { useEffect, useState } from 'react';
import { AUTH_REQUIRED_EVENT, setApiToken, clearApiToken } from '../api/client';

// One-time token prompt (D1). Shown when apiFetch sees a 401. The token is stored in
// sessionStorage via setApiToken. Save retries the failed request when the caller passes
// `retry`, otherwise it reloads the page. Dismissing hides the prompt until the next 401.

export interface TokenGateProps {
  /** Optional override for the post-save action. Defaults to reloading the page. */
  onSaved?: () => void;
}

export const TokenGate: React.FC<TokenGateProps> = ({ onSaved }) => {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handler = () => {
      setError(null);
      setOpen(true);
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, handler);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, handler);
  }, []);

  if (!open) return null;

  const close = () => {
    setValue('');
    setError(null);
    setOpen(false);
  };

  const save = (e?: React.FormEvent) => {
    e?.preventDefault();
    const token = value.trim();
    if (!token) {
      setError('Paste the API token from ~/.antikythera/api_token.');
      return;
    }
    setApiToken(token);
    setValue('');
    setOpen(false);
    if (onSaved) {
      onSaved();
    } else {
      window.location.reload();
    }
  };

  const forget = () => {
    clearApiToken();
    close();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="token-gate-title"
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-[70]"
    >
      <form
        onSubmit={save}
        className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 space-y-4"
      >
        <h2 id="token-gate-title" className="text-xl font-bold text-gray-900">
          API token required
        </h2>
        <p className="text-sm text-gray-600">
          The backend rejected the request as unauthorized. Paste the API token (stored in
          <code className="mx-1">~/.antikythera/api_token</code>). It is kept for this browser
          session only.
        </p>
        <label className="block text-sm font-medium text-gray-700" htmlFor="token-gate-input">
          Token
        </label>
        <input
          id="token-gate-input"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 font-mono text-sm"
        />
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={close}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            Dismiss
          </button>
          <button
            type="button"
            onClick={forget}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            Clear saved token
          </button>
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Save
          </button>
        </div>
      </form>
    </div>
  );
};

export default TokenGate;
