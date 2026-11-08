import React, { useState } from 'react';
import { apiUrl } from '../config';
import { setApiToken } from '../api/client';

// First-run setup wizard (D9). Shown by App when GET /api/setup/status reports incomplete.
// This screen runs before any API token exists, so every request is a plain fetch.
// Secret inputs are masked and only typed values are sent. Values are never read back:
// the status endpoint reports presence only.

export interface SetupItem {
  id: string;
  kind: string;
  name: string;
  label: string;
  ok: boolean;
  state: string;
  settable: boolean;
  secret: boolean;
}

export interface SetupStatus {
  complete: boolean;
  items: SetupItem[];
  /** True while the one-time setup secret exists (P0-1). Gates the writes. */
  setup_secret_required?: boolean;
}

export interface SetupScreenProps {
  /** Called after the wizard is finished. */
  onComplete?: () => void;
}

const SECTIONS: { kind: string; title: string; blurb: string }[] = [
  { kind: 'env_file', title: 'Environment file', blurb: 'The plain settings file on this host.' },
  { kind: 'provider_key', title: 'AI provider keys', blurb: 'Stored in the secrets file. Leave blank to keep the current value.' },
  { kind: 'jira', title: 'Jira', blurb: 'Base URL is stored in the settings file. The personal access token is a secret.' },
  { kind: 'slack', title: 'Slack notifications', blurb: 'Incoming webhook URL. Stored as a secret.' },
  { kind: 'api_token', title: 'API token', blurb: 'Required by every API call once setup finishes.' },
  { kind: 'port', title: 'Ports', blurb: 'The API port. Changing it needs a restart.' },
  { kind: 'origins', title: 'Allowed origins', blurb: 'Browser origins allowed to call the API.' },
  { kind: 'data_dir', title: 'Data directory', blurb: 'Where pipeline state is kept.' },
  { kind: 'backup_dir', title: 'Backups', blurb: 'Directory for nightly data backups.' },
];

const SETUP_BASE = `${apiUrl}/api/setup`;

const describeState = (item: SetupItem): string => {
  if (item.kind === 'env_file') return item.ok ? 'Present' : 'Not found';
  if (item.kind === 'api_token') return item.ok ? 'Generated' : 'Not generated yet';
  if (item.kind === 'data_dir') {
    if (item.state === 'writable') return 'Present and writable';
    if (item.state === 'read_only') return 'Present but not writable';
    return 'Missing';
  }
  if (item.kind === 'port' || item.kind === 'origins') return item.state === 'custom' ? 'Custom' : 'Default';
  return item.ok ? 'Set' : 'Not set';
};

export const SetupScreen: React.FC<SetupScreenProps> = ({ onComplete }) => {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [setupSecret, setSetupSecret] = useState('');

  const load = async () => {
    try {
      const res = await fetch(`${SETUP_BASE}/status`);
      if (res.status === 403) {
        setLoadError('Setup is only available from the local machine. Open the UI through the host tunnel on this machine.');
        return;
      }
      if (res.status === 404) {
        setLoadError('Setup is already complete. Reload the page.');
        return;
      }
      if (!res.ok) throw new Error(`status ${res.status}`);
      setStatus(await res.json());
      setLoadError(null);
    } catch (e) {
      setLoadError('Could not read setup status. Check that the backend is running on this machine.');
    }
  };

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setValue = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  // Only keys the user typed a non-blank value for are sent.
  const typedUpdates = (): Record<string, string> => {
    const out: Record<string, string> = {};
    for (const [key, raw] of Object.entries(values)) {
      const trimmed = raw.trim();
      if (trimmed) out[key] = trimmed;
    }
    return out;
  };

  // P0-1: while a setup secret exists, both write endpoints require the
  // X-Setup-Secret header (constant-time compared server-side). Plain fetch
  // stays: these calls are pre-token by design.
  const secretHeaders = (): Record<string, string> =>
    status?.setup_secret_required ? { 'X-Setup-Secret': setupSecret.trim() } : {};

  const secretRejected = (): void => {
    setError('The setup secret was not accepted. It is printed in the backend log at first start.');
  };

  const saveConfig = async (): Promise<boolean> => {
    const updates = typedUpdates();
    if (Object.keys(updates).length === 0) return true;
    const res = await fetch(`${SETUP_BASE}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...secretHeaders() },
      body: JSON.stringify(updates),
    });
    if (!res.ok) {
      if (res.status === 403) {
        secretRejected();
        return false;
      }
      const body = await res.json().catch(() => ({}));
      setError(typeof body.detail === 'string' ? body.detail : `Saving failed (${res.status}).`);
      return false;
    }
    setValues({});
    return true;
  };

  const finish = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await saveConfig();
      if (!saved) return;
      const res = await fetch(`${SETUP_BASE}/complete`, {
        method: 'POST',
        headers: secretHeaders(),
      });
      if (!res.ok) {
        if (res.status === 403) {
          secretRejected();
          return;
        }
        setError(`Finishing setup failed (${res.status}).`);
        return;
      }
      const body = await res.json().catch(() => ({}));
      if (typeof body.api_token === 'string' && body.api_token) {
        setGeneratedToken(body.api_token);
        setMessage('Setup is saved. Copy the API token now; it is shown only once.');
      } else {
        setMessage('Setup is saved.');
        onComplete?.();
      }
    } catch (e) {
      setError('Could not reach the backend. Setup is not finished.');
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (await saveConfig()) {
        setMessage('Saved. Values are written to the local settings files.');
        await load();
      }
    } catch (e) {
      setError('Could not reach the backend. Nothing was saved.');
    } finally {
      setBusy(false);
    }
  };

  const copyToken = async () => {
    if (!generatedToken) return;
    try {
      await navigator.clipboard.writeText(generatedToken);
      setCopied(true);
    } catch {
      setError('Copy failed. Select the token and copy it manually.');
    }
  };

  const itemsOf = (kind: string) => (status?.items ?? []).filter((i) => i.kind === kind);

  const renderField = (item: SetupItem) => {
    if (!item.settable) return null;
    const key = item.name;
    const isSecret = item.secret;
    const placeholder = item.ok
      ? (isSecret ? 'Set. Type a new value to replace it.' : 'Set. Type to change.')
      : 'Not set';
    return (
      <div key={item.id} className="space-y-1">
        <label htmlFor={`setup-${item.id}`} className="block text-sm font-medium text-gray-700">
          {item.label} <span className="text-xs text-gray-500">({item.name})</span>
        </label>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>{describeState(item)}</span>
        </div>
        <input
          id={`setup-${item.id}`}
          name={key}
          type={isSecret ? 'password' : 'text'}
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={values[key] ?? ''}
          onChange={(e) => setValue(key, e.target.value)}
          className="block w-full border-gray-300 rounded-md shadow-sm focus:ring-teal-500 focus:border-teal-500"
        />
      </div>
    );
  };

  if (generatedToken) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div role="dialog" aria-labelledby="setup-token-title" className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6 space-y-4">
          <h2 id="setup-token-title" className="text-xl font-bold text-gray-900">Your API token</h2>
          <p className="text-sm text-gray-600">
            Copy this token and keep it safe. The browser uses it for every request. It is also stored
            in <code className="mx-1">~/.antikythera/api_token</code> on the host. It will not be shown again.
          </p>
          <code data-testid="setup-generated-token" className="block break-all bg-gray-100 rounded p-3 text-sm text-gray-900">
            {generatedToken}
          </code>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={copyToken}
              className="px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700 transition"
            >
              {copied ? 'Copied' : 'Copy token'}
            </button>
            <button
              type="button"
              onClick={() => {
                // Keep the token for this browser session so the app can call the API now.
                setApiToken(generatedToken);
                setGeneratedToken(null);
                onComplete?.();
              }}
              disabled={!copied}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition disabled:opacity-50"
            >
              I have saved the token
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-3xl mx-auto bg-white rounded-lg shadow p-6 space-y-6">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold text-gray-900">Set up Antikythera</h1>
          <p className="text-sm text-gray-600">
            Each section lists what is configured. Secrets are never shown back. Leave a field blank to keep
            its current value.
          </p>
        </header>

        {loadError && (
          <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            {loadError}
            <button type="button" onClick={load} className="ml-3 underline">Retry</button>
          </div>
        )}

        {status?.setup_secret_required && (
          <section className="space-y-1 border-t border-gray-200 pt-4">
            <label htmlFor="setup-secret" className="block text-sm font-medium text-gray-900">
              Setup secret
            </label>
            <p className="text-xs text-gray-500">In the setup_secret file under the Antikythera config directory on the server (the first-start log line names its path).</p>
            <input
              id="setup-secret"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Setup secret"
              value={setupSecret}
              onChange={(e) => setSetupSecret(e.target.value)}
              className="block w-full border-gray-300 rounded-md shadow-sm focus:ring-teal-500 focus:border-teal-500"
            />
          </section>
        )}

        {status &&
          SECTIONS.map((section) => {
            const items = itemsOf(section.kind);
            if (items.length === 0) return null;
            return (
              <section key={section.kind} aria-labelledby={`setup-section-${section.kind}`} className="space-y-3 border-t border-gray-200 pt-4">
                <div>
                  <h2 id={`setup-section-${section.kind}`} className="text-lg font-semibold text-gray-900">
                    {section.title}
                  </h2>
                  <p className="text-sm text-gray-500">{section.blurb}</p>
                </div>
                {items.map((item) =>
                  item.settable ? (
                    renderField(item)
                  ) : (
                    <div key={item.id} className="text-sm text-gray-700">
                      {item.label}: <span className="font-medium">{describeState(item)}</span>
                    </div>
                  ),
                )}
              </section>
            );
          })}

        {status && (
          <div className="flex flex-wrap items-center gap-3 border-t border-gray-200 pt-4">
            <button
              type="button"
              onClick={save}
              disabled={busy}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition disabled:opacity-50"
            >
              Save
            </button>
            <button
              type="button"
              onClick={finish}
              disabled={busy}
              className="px-4 py-2 bg-teal-600 text-white rounded hover:bg-teal-700 transition disabled:opacity-50"
            >
              Finish setup
            </button>
          </div>
        )}

        {message && <p role="status" className="text-sm text-teal-700">{message}</p>}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        {!status && !loadError && <p className="text-sm text-gray-500">Loading setup status...</p>}
      </div>
    </div>
  );
};

export default SetupScreen;
