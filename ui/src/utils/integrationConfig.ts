// Helpers for showing and saving integration configs without exposing or re-sending masked secrets.

// Placeholder the server returns for secret values (api/integration_hub.py MASK_PLACEHOLDER).
export const MASK_PLACEHOLDER = '*****';

// Mirrors the server's segment-based secret detection (api/integration_hub.py _is_secret_key).
const SECRET_SEGMENTS = new Set([
  'token', 'pat', 'password', 'passwd', 'pwd', 'secret', 'key', 'apikey', 'credential', 'credentials',
]);

export function isSecretKey(name: string): boolean {
  return name.toLowerCase().split(/[_\-. ]+/).some(seg => SECRET_SEGMENTS.has(seg));
}

function isPlainObject(v: unknown): v is Record<string, any> {
  return !!v && typeof v === 'object' && !Array.isArray(v);
}

/**
 * Editor view of a config: helper keys removed; secret-looking values, jira_url/url and every
 * env value shown as MASK_PLACEHOLDER (empty values stay empty so the UI can show "not set").
 * The placeholder is display-only: stripMasked() removes it again before a save.
 */
export function maskForEditor(cfg: Record<string, any> | null | undefined): Record<string, any> {
  const copy: Record<string, any> = { ...(cfg ?? {}) };
  delete copy.test;
  for (const key of Object.keys(copy)) {
    const value = copy[key];
    if (key === 'env' && isPlainObject(value)) {
      copy[key] = Object.fromEntries(
        Object.entries(value).map(([k, v]) => [k, v ? MASK_PLACEHOLDER : v]),
      );
    } else if ((isSecretKey(key) || key === 'jira_url' || key === 'url') && value) {
      copy[key] = MASK_PLACEHOLDER;
    }
  }
  return copy;
}

/** Drop masked placeholders (top level and inside env) so the stored secret is kept by the server. */
export function stripMasked(cfg: Record<string, any>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [key, value] of Object.entries(cfg)) {
    if (value === MASK_PLACEHOLDER) continue;
    if (key === 'env' && isPlainObject(value)) {
      out[key] = Object.fromEntries(Object.entries(value).filter(([, v]) => v !== MASK_PLACEHOLDER));
    } else {
      out[key] = value;
    }
  }
  return out;
}
