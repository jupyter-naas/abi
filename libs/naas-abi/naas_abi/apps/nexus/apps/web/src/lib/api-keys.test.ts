import { describe, expect, it, vi } from 'vitest';
import {
  ACCESS_LABELS,
  ApiKey,
  ApiKeysError,
  activeKeyCount,
  createApiKey,
  formatKeyDate,
  listApiKeys,
  parseScopeJson,
  revokeApiKey,
  usageExamples,
} from './api-keys';

const key = (over: Partial<ApiKey> = {}): ApiKey => ({
  id: 'abcdefghijklmnop',
  name: 'CI',
  prefix: 'abi_pk_abcdefghijklmnop',
  created_at: '2026-10-01T10:00:00Z',
  expires_at: '2027-10-01T10:00:00Z',
  last_used_at: null,
  revoked_at: null,
  status: 'active',
  access: 'full',
  scope: null,
  ...over,
});

const reply = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('listApiKeys', () => {
  it('reads the keys of the signed-in user', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply(200, [key()]));
    expect(await listApiKeys(fetcher)).toEqual([key()]);
    expect(fetcher).toHaveBeenCalledWith('/api/iam/api-keys');
  });

  it('says what went wrong', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply(500, {}));
    await expect(listApiKeys(fetcher)).rejects.toMatchObject({
      name: 'ApiKeysError',
      status: 500,
      message: 'Could not load your API keys.',
    });
  });

  it('knows when the server keeps no keys', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply(503, { detail: 'API keys need IAM' }));
    await expect(listApiKeys(fetcher)).rejects.toThrow('not available on this server');
  });
});

describe('createApiKey', () => {
  it('sends the name, the expiry and the access, and returns the secret once', async () => {
    const created = { key: key(), secret: 'abi_pk_abcdefghijklmnop_s3cret' };
    const fetcher = vi.fn().mockResolvedValue(reply(201, created));
    const result = await createApiKey(
      { name: '  CI  ', expiresInDays: 90, access: 'read', scope: [] },
      fetcher,
    );
    expect(result).toEqual(created);
    const [url, options] = fetcher.mock.calls[0];
    expect(url).toBe('/api/iam/api-keys');
    expect(options.method).toBe('POST');
    // A read-only key names no statements: the server builds them.
    expect(JSON.parse(options.body)).toEqual({ name: 'CI', expires_in_days: 90, access: 'read' });
  });

  it('sends the statements of a custom key', async () => {
    const scope = [{ effect: 'Allow' as const, actions: ['a:B'], resources: ['*'] }];
    const fetcher = vi.fn().mockResolvedValue(reply(201, { key: key(), secret: 's' }));
    await createApiKey({ name: 'x', expiresInDays: 30, access: 'custom', scope }, fetcher);
    expect(JSON.parse(fetcher.mock.calls[0][1].body).scope).toEqual(scope);
  });

  it('explains the limit of active keys', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply(409, {}));
    const error = await createApiKey({ name: 'x', expiresInDays: 30, access: 'full' }, fetcher).catch(
      (e) => e,
    );
    expect(error).toBeInstanceOf(ApiKeysError);
    expect(error.status).toBe(409);
    expect(error.message).toContain('5 active keys');
  });

  it("shows the server's words for invalid input", async () => {
    const fetcher = vi.fn().mockResolvedValue(reply(422, { detail: 'A key needs a name' }));
    await expect(
      createApiKey({ name: ' ', expiresInDays: 30, access: 'full' }, fetcher),
    ).rejects.toThrow('A key needs a name');
  });
});

describe('revokeApiKey', () => {
  it('revokes by id, encoded', async () => {
    const revoked = key({ status: 'revoked', revoked_at: '2026-10-02T00:00:00Z' });
    const fetcher = vi.fn().mockResolvedValue(reply(200, revoked));
    expect(await revokeApiKey('a/b', fetcher)).toEqual(revoked);
    expect(fetcher).toHaveBeenCalledWith('/api/iam/api-keys/a%2Fb', { method: 'DELETE' });
  });

  it('reports a key that is not theirs', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply(404, { detail: 'API key not found' }));
    await expect(revokeApiKey('x', fetcher)).rejects.toMatchObject({ status: 404 });
  });
});

describe('parseScopeJson', () => {
  const good = '[{"effect":"Allow","actions":["triple_store:Query"],"resources":["*"]}]';

  it('accepts a list of Allow statements', () => {
    expect(parseScopeJson(good)).toEqual({
      ok: true,
      scope: [{ effect: 'Allow', actions: ['triple_store:Query'], resources: ['*'] }],
    });
  });

  it.each([
    ['not json', 'not valid JSON'],
    ['{}', 'array'],
    ['[]', 'at least one'],
    ['["x"]', 'must be an object'],
    ['[{"effect":"Deny","actions":["a:B"],"resources":["*"]}]', 'Allow'],
    ['[{"effect":"Allow","actions":"a:B","resources":["*"]}]', 'actions must be a list'],
    ['[{"effect":"Allow","actions":["a:B"]}]', 'resources must be a list'],
    ['[{"effect":"Allow","actions":[""],"resources":["*"]}]', 'non-empty'],
  ])('refuses %s', (text, message) => {
    const result = parseScopeJson(text);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain(message);
  });

  it('names the statement that is wrong', () => {
    const result = parseScopeJson(`[${good.slice(1, -1)}, {"effect":"Allow"}]`);
    expect(result).toMatchObject({ ok: false });
    if (!result.ok) expect(result.error).toContain('Statement 2');
  });
});

describe('helpers', () => {
  it('counts the keys that still work', () => {
    expect(
      activeKeyCount([key(), key({ status: 'revoked' }), key({ status: 'expired' }), key()]),
    ).toBe(2);
  });

  it('writes a date, or a word for none', () => {
    expect(formatKeyDate(null, 'Never')).toBe('Never');
    expect(formatKeyDate('garbage', 'Never')).toBe('Never');
    expect(formatKeyDate('2026-10-01T10:00:00Z', 'Never')).not.toBe('Never');
  });

  it('labels the three kinds of access', () => {
    expect(ACCESS_LABELS).toEqual({ full: 'Full access', read: 'Read only', custom: 'Custom' });
  });

  it('shows how to use a key, with the API origin', () => {
    const { bearer, token } = usageExamples('abi_pk_x', 'https://api.example.com/');
    expect(bearer).toContain('Authorization: Bearer abi_pk_x');
    expect(bearer).toContain('https://api.example.com/api/workspaces');
    expect(token).toContain('https://api.example.com/api/iam/token');
    expect(token).toContain('grant_type=client_credentials');
    expect(token).toContain('client_secret=abi_pk_x');
  });
});
