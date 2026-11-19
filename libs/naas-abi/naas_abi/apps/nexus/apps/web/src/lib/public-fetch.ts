/**
 * A server-side GET that reaches the public internet only.
 *
 * For the web app's routes that fetch a URL a page gives them
 * (`/api/image-data`, `/api/link-preview`):
 *
 * - `https` on the default port only, with no credentials in the URL;
 * - every address the host resolves to must be public: no loopback, private,
 *   carrier-grade NAT, link-local (cloud metadata), multicast, reserved or
 *   documentation range, IPv4 or IPv6, and the connection goes to the very
 *   address that was checked (a second lookup cannot answer differently);
 * - each redirect is a new request, checked the same way, three at most;
 * - the answer is capped in size and the whole exchange in time.
 *
 * Anything else throws `PublicFetchRefused` before a byte is sent.
 */

import { lookup } from 'node:dns/promises';
import https from 'node:https';
import { BlockList, isIP } from 'node:net';

export class PublicFetchRefused extends Error {}

// One list per family: a single BlockList would match IPv4 addresses against the
// IPv4-mapped IPv6 range below, and refuse them all.
const NOT_PUBLIC_V4 = new BlockList();
const NOT_PUBLIC_V6 = new BlockList();
for (const [network, prefix] of [
  ['0.0.0.0', 8],
  ['10.0.0.0', 8],
  ['100.64.0.0', 10],
  ['127.0.0.0', 8],
  ['169.254.0.0', 16],
  ['172.16.0.0', 12],
  ['192.0.0.0', 24],
  ['192.0.2.0', 24],
  ['192.88.99.0', 24],
  ['192.168.0.0', 16],
  ['198.18.0.0', 15],
  ['198.51.100.0', 24],
  ['203.0.113.0', 24],
  ['224.0.0.0', 4],
  ['240.0.0.0', 4],
] as const) {
  NOT_PUBLIC_V4.addSubnet(network, prefix, 'ipv4');
}
for (const [network, prefix] of [
  ['::', 128],
  ['::1', 128],
  ['::ffff:0:0', 96], // IPv4-mapped: the IPv4 address decides, so none is taken
  ['64:ff9b::', 96], // NAT64
  ['64:ff9b:1::', 48],
  ['100::', 64],
  ['2001::', 23], // IETF protocol assignments (Teredo, ORCHID, ...)
  ['2001:db8::', 32],
  ['2002::', 16], // 6to4: embeds an IPv4 address
  ['fc00::', 7],
  ['fe80::', 10],
  ['fec0::', 10],
  ['ff00::', 8],
] as const) {
  NOT_PUBLIC_V6.addSubnet(network, prefix, 'ipv6');
}

/** Whether `address` (an IP literal) is an address of the public internet. */
export function isPublicAddress(address: string): boolean {
  const family = isIP(address);
  if (family === 4) return !NOT_PUBLIC_V4.check(address, 'ipv4');
  if (family === 6) return !NOT_PUBLIC_V6.check(address, 'ipv6');
  return false;
}

export type PublicFetchResult = {
  status: number;
  contentType: string;
  body: Buffer;
  url: string;
};

type Exchange = { status: number; headers: Record<string, string | string[] | undefined>; body: Buffer };

export type PublicFetchOptions = {
  maxBytes: number;
  timeoutMs: number;
  maxRedirects?: number;
  headers?: Record<string, string>;
  /** The host's addresses (tests). Default: every address DNS gives. */
  resolve?: (hostname: string) => Promise<string[]>;
  /** One request to `url`, connected to `address` (tests). Default: `node:https`. */
  send?: (url: URL, address: string, options: SendOptions) => Promise<Exchange>;
};

type SendOptions = { headers: Record<string, string>; maxBytes: number; signal: AbortSignal };

async function resolveAll(hostname: string): Promise<string[]> {
  const found = await lookup(hostname, { all: true, verbatim: true });
  return found.map((entry) => entry.address);
}

function send(url: URL, address: string, options: SendOptions): Promise<Exchange> {
  return new Promise((resolve, reject) => {
    const req = https.request(
      url,
      {
        method: 'GET',
        headers: options.headers,
        signal: options.signal,
        // The connection goes to the address that was checked, whatever DNS says now.
        lookup: ((_host: string, opts: { all?: boolean }, callback: (...args: unknown[]) => void) => {
          const family = isIP(address);
          if (opts?.all) callback(null, [{ address, family }]);
          else callback(null, address, family);
        }) as unknown as https.RequestOptions['lookup'],
      },
      (res) => {
        const chunks: Buffer[] = [];
        let size = 0;
        res.on('data', (chunk: Buffer) => {
          size += chunk.length;
          if (size > options.maxBytes) {
            req.destroy(new PublicFetchRefused('The answer is too large'));
            return;
          }
          chunks.push(chunk);
        });
        res.on('end', () =>
          resolve({ status: res.statusCode ?? 0, headers: res.headers, body: Buffer.concat(chunks) }),
        );
        res.on('error', reject);
      },
    );
    req.on('error', reject);
    req.end();
  });
}

/** The URL a request may go to, or a refusal. */
function checkedUrl(raw: string | URL, base?: URL): URL {
  let url: URL;
  try {
    url = new URL(raw, base);
  } catch {
    throw new PublicFetchRefused('Not a URL');
  }
  if (url.protocol !== 'https:') throw new PublicFetchRefused('Only https is fetched');
  if (url.username || url.password) throw new PublicFetchRefused('No credentials in the URL');
  if (url.port && url.port !== '443') throw new PublicFetchRefused('Only the default port');
  return url;
}

async function publicAddressOf(url: URL, resolve: (hostname: string) => Promise<string[]>): Promise<string> {
  const host = url.hostname.replace(/^\[(.*)\]$/, '$1');
  let addresses: string[];
  if (isIP(host)) {
    addresses = [host];
  } else {
    try {
      addresses = await resolve(host);
    } catch {
      throw new PublicFetchRefused('The host does not resolve');
    }
  }
  if (addresses.length === 0 || !addresses.every(isPublicAddress)) {
    throw new PublicFetchRefused('The host is not on the public internet');
  }
  return addresses[0];
}

function header(headers: Exchange['headers'], name: string): string {
  const value = headers[name];
  return Array.isArray(value) ? value[0] ?? '' : value ?? '';
}

/** GET `raw` on the public internet, following at most `maxRedirects` checked redirects. */
export async function fetchPublic(raw: string, options: PublicFetchOptions): Promise<PublicFetchResult> {
  const resolve = options.resolve ?? resolveAll;
  const sendOne = options.send ?? send;
  const maxRedirects = options.maxRedirects ?? 3;
  const signal = AbortSignal.timeout(options.timeoutMs);
  let url = checkedUrl(raw);
  for (let hop = 0; ; hop++) {
    const address = await publicAddressOf(url, resolve);
    if (signal.aborted) throw new PublicFetchRefused('Too slow');
    const answer = await sendOne(url, address, {
      headers: { 'User-Agent': 'NexusWeb/1.0', ...(options.headers ?? {}) },
      maxBytes: options.maxBytes,
      signal,
    });
    const location = header(answer.headers, 'location');
    if (answer.status >= 300 && answer.status < 400 && location) {
      if (hop >= maxRedirects) throw new PublicFetchRefused('Too many redirects');
      url = checkedUrl(location, url);
      continue;
    }
    if (answer.body.length > options.maxBytes) throw new PublicFetchRefused('The answer is too large');
    return {
      status: answer.status,
      contentType: header(answer.headers, 'content-type'),
      body: answer.body,
      url: url.toString(),
    };
  }
}
