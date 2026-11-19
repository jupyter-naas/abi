import { describe, expect, it, vi } from 'vitest';

import { fetchPublic, isPublicAddress, PublicFetchRefused, type PublicFetchOptions } from './public-fetch';

const PUBLIC = '93.184.215.14';

type Send = NonNullable<PublicFetchOptions['send']>;

function answers(...replies: Array<{ status: number; location?: string; type?: string; body?: string }>) {
  const sent: Array<{ url: string; address: string }> = [];
  const send: Send = vi.fn(async (url, address) => {
    sent.push({ url: url.toString(), address });
    const reply = replies.shift();
    if (!reply) throw new Error('no more replies');
    return {
      status: reply.status,
      headers: {
        ...(reply.location ? { location: reply.location } : {}),
        'content-type': reply.type ?? 'image/png',
      },
      body: Buffer.from(reply.body ?? 'png'),
    };
  });
  return { send, sent };
}

const resolveTo =
  (table: Record<string, string[]>) =>
  async (host: string): Promise<string[]> =>
    table[host] ?? [PUBLIC];

const options = (send: Send, resolve = resolveTo({})): PublicFetchOptions => ({
  maxBytes: 1024,
  timeoutMs: 2000,
  send,
  resolve,
});

describe('public fetch', () => {
  it('keeps every non-public address out', () => {
    for (const address of [
      '127.0.0.1',
      '10.1.2.3',
      '172.17.0.2',
      '192.168.1.1',
      '169.254.169.254',
      '100.64.0.1',
      '0.0.0.0',
      '224.0.0.1',
      '::1',
      '::',
      'fd00::1',
      'fe80::1',
      '::ffff:127.0.0.1',
      '::ffff:7f00:1',
      '64:ff9b::a00:1',
      '2002:7f00:1::',
      'not-an-ip',
    ]) {
      expect(isPublicAddress(address), address).toBe(false);
    }
    expect(isPublicAddress(PUBLIC)).toBe(true);
    expect(isPublicAddress('2606:4700:4700::1111')).toBe(true);
  });

  it('keeps requests on https, the default port and no credentials', async () => {
    const { send, sent } = answers();
    for (const url of [
      'http://example.com/a.png',
      'ftp://example.com/a.png',
      'https://example.com:8443/a.png',
      'https://user:pw@example.com/a.png',
      'not a url',
    ]) {
      await expect(fetchPublic(url, options(send))).rejects.toBeInstanceOf(PublicFetchRefused);
    }
    expect(sent).toEqual([]);
  });

  it('keeps hosts that resolve to an internal address unreached', async () => {
    const { send, sent } = answers();
    const resolve = resolveTo({
      'internal.example': ['10.0.0.5'],
      'mixed.example': [PUBLIC, '127.0.0.1'],
      'nothing.example': [],
    });
    for (const url of [
      'https://127.0.0.1/internal',
      'https://[::1]/internal',
      'https://169.254.169.254/latest/meta-data/',
      'https://internal.example/x.png',
      'https://mixed.example/x.png',
      'https://nothing.example/x.png',
    ]) {
      await expect(fetchPublic(url, options(send, resolve))).rejects.toBeInstanceOf(PublicFetchRefused);
    }
    expect(sent).toEqual([]);
  });

  it('keeps each redirect hop to the same rules', async () => {
    for (const location of [
      'https://127.0.0.1/internal',
      'http://example.org/x.png',
      'https://internal.example/x.png',
    ]) {
      const { send, sent } = answers({ status: 302, location });
      await expect(
        fetchPublic('https://example.com/x.png', options(send, resolveTo({ 'internal.example': ['192.168.0.9'] }))),
      ).rejects.toBeInstanceOf(PublicFetchRefused);
      expect(sent).toEqual([{ url: 'https://example.com/x.png', address: PUBLIC }]);
    }
  });

  it('keeps redirects few, answers small, and follows a public redirect', async () => {
    const loop = answers(...Array.from({ length: 5 }, () => ({ status: 302, location: '/again' })));
    await expect(fetchPublic('https://example.com/x.png', options(loop.send))).rejects.toThrow('Too many redirects');
    expect(loop.sent).toHaveLength(4);

    const large = answers({ status: 200, body: 'x'.repeat(2048) });
    await expect(fetchPublic('https://example.com/x.png', options(large.send))).rejects.toThrow('too large');

    const moved = answers({ status: 301, location: 'https://cdn.example/y.png' }, { status: 200, body: 'png' });
    const result = await fetchPublic('https://example.com/x.png', options(moved.send));
    expect(result).toMatchObject({ status: 200, contentType: 'image/png', url: 'https://cdn.example/y.png' });
    expect(result.body.toString()).toBe('png');
  });
});
