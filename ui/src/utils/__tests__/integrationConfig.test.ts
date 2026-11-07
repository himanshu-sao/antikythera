import { describe, test, expect } from 'vitest';
import { MASK_PLACEHOLDER, isSecretKey, maskForEditor, stripMasked } from '../integrationConfig';

describe('isSecretKey', () => {
  test.each([
    ['token', true],
    ['access_token', true],
    ['api_key', true],
    ['password', true],
    ['client-secret', true],
    ['PAT', true],
    ['path', false],
    ['adapter_module', false],
    ['jira_url', false],
  ])('%s -> %s', (name, expected) => {
    expect(isSecretKey(name)).toBe(expected);
  });
});

describe('maskForEditor', () => {
  test('masks secret keys and jira_url/url, removes the test flag, leaves other keys alone', () => {
    const out = maskForEditor({
      adapter_module: 'api.adapters.jira',
      token: 'real-token',
      jira_url: 'https://x.atlassian.net',
      url: 'https://mcp.local',
      test: true,
      enabled: true,
    });
    expect(out).toEqual({
      adapter_module: 'api.adapters.jira',
      token: MASK_PLACEHOLDER,
      jira_url: MASK_PLACEHOLDER,
      url: MASK_PLACEHOLDER,
      enabled: true,
    });
  });

  test('empty secret values stay empty so the UI can show "not set"', () => {
    expect(maskForEditor({ token: '', api_key: null })).toEqual({ token: '', api_key: null });
  });

  test('every non-empty env value is masked, empty ones are kept', () => {
    const out = maskForEditor({ env: { GITHUB_TOKEN: 'abc', EMPTY: '' } });
    expect(out.env).toEqual({ GITHUB_TOKEN: MASK_PLACEHOLDER, EMPTY: '' });
  });

  test('handles null/undefined config', () => {
    expect(maskForEditor(null)).toEqual({});
    expect(maskForEditor(undefined)).toEqual({});
  });

  test('does not mutate the input', () => {
    const input = { token: 'secret' };
    maskForEditor(input);
    expect(input.token).toBe('secret');
  });
});

describe('stripMasked', () => {
  test('drops masked top-level values so the server keeps the stored secret', () => {
    expect(stripMasked({ adapter_module: 'a', token: MASK_PLACEHOLDER, enabled: false })).toEqual({
      adapter_module: 'a',
      enabled: false,
    });
  });

  test('drops masked env values but keeps real ones', () => {
    expect(stripMasked({ env: { A: MASK_PLACEHOLDER, B: 'new' } })).toEqual({ env: { B: 'new' } });
  });

  test('keeps a newly typed secret', () => {
    expect(stripMasked({ token: 'typed-by-user' })).toEqual({ token: 'typed-by-user' });
  });

  test('round-trip: maskForEditor then stripMasked removes exactly the masked keys', () => {
    const stored = { adapter_module: 'x', token: 'secret', env: { K: 'v' } };
    const roundTrip = stripMasked(maskForEditor(stored));
    expect(roundTrip).toEqual({ adapter_module: 'x', env: {} });
    expect(JSON.stringify(roundTrip)).not.toContain('secret');
  });
});
