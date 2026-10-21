import { NextRequest } from 'next/server';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GET, POST } from './route';

const params = { params: { path: ['some', 'module', 'console', 'api', 'uploads'] } };

function upstreamCall(fetchMock: ReturnType<typeof vi.fn>): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return { url, init };
}

function stubFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async () => new Response('{}', { status: 201, headers: { 'content-type': 'application/json' } }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe('app-html proxy', () => {
  it('forwards a multipart body with its content type, so the upstream can read the boundary', async () => {
    const fetchMock = stubFetch();
    const form = new FormData();
    form.append('name', 'reports');
    form.append('files', new Blob(['%PDF-1.4'], { type: 'application/pdf' }), 'report.pdf');
    const outgoing = new Request('https://nexus.example/app-html/some/module/console/api/uploads?token=jwt', {
      method: 'POST',
      body: form,
    });
    const contentType = outgoing.headers.get('content-type') ?? '';
    const request = new NextRequest(outgoing.url, {
      method: 'POST',
      headers: outgoing.headers,
      body: await outgoing.arrayBuffer(),
    });

    const res = await POST(request, params);

    expect(res.status).toBe(201);
    const { init } = upstreamCall(fetchMock);
    const headers = new Headers(init.headers);
    expect(contentType).toMatch(/^multipart\/form-data; boundary=/);
    expect(headers.get('content-type')).toBe(contentType);
    expect(headers.get('authorization')).toBe('Bearer jwt');
    // The body streams to the upstream, never read whole here.
    expect(init.body).toBeInstanceOf(ReadableStream);
    const forwarded = await new Response(init.body as ReadableStream).text();
    expect(forwarded).toContain('name="files"; filename="report.pdf"');
  });

  it('forwards a JSON content type and the accepted response types', async () => {
    const fetchMock = stubFetch();
    const request = new NextRequest('https://nexus.example/app-html/some/module/console/api/rebuild', {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json', authorization: 'Bearer jwt' },
      body: JSON.stringify({ events: true }),
    });

    await POST(request, params);

    const headers = new Headers(upstreamCall(fetchMock).init.headers);
    expect(headers.get('content-type')).toBe('application/json');
    expect(headers.get('accept')).toBe('application/json');
  });

  it('sends no body and no content type on GET', async () => {
    const fetchMock = stubFetch();
    const request = new NextRequest('https://nexus.example/app-html/some/module/console/index.html?token=jwt');

    await GET(request, params);

    const { init } = upstreamCall(fetchMock);
    expect(init.body).toBeUndefined();
    expect(new Headers(init.headers).has('content-type')).toBe(false);
  });
});

describe('app-html proxy and remote module apps', () => {
  it('sends a remote app link to its grant URL on the API origin', async () => {
    vi.stubEnv('NEXUS_API_URL', 'https://api.nexus.example/');
    const fetchMock = vi.fn(
      async () =>
        new Response(null, {
          status: 307,
          headers: { location: '/app-remote/g.r.ant/acme.research/console/index.html?q=1' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const request = new NextRequest(
      'https://nexus.example/app-html/remote/acme.research/console/index.html?token=jwt&q=1',
    );

    const res = await GET(request, { params: { path: ['remote', 'acme.research', 'console', 'index.html'] } });

    expect(res.status).toBe(307);
    expect(res.headers.get('location')).toBe(
      'https://api.nexus.example/app-remote/g.r.ant/acme.research/console/index.html?q=1',
    );
    const { url, init } = upstreamCall(fetchMock);
    expect(url).toMatch(/\/app-html\/remote\/acme\.research\/console\/index\.html\?token=jwt&q=1$/);
    expect(new Headers(init.headers).get('authorization')).toBe('Bearer jwt');
  });

  it('passes a redirect on to the browser instead of following it', async () => {
    const fetchMock = vi.fn(
      async () => new Response(null, { status: 302, headers: { location: '/app-html/some/module/console/' } }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const request = new NextRequest('https://nexus.example/app-html/some/module/console?token=jwt');

    const res = await GET(request, params);

    expect(upstreamCall(fetchMock).init.redirect).toBe('manual');
    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe('/app-html/some/module/console/');
  });

  it('keeps the upstream sandbox and referrer policy', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response('<html></html>', {
          status: 200,
          headers: {
            'content-type': 'text/html',
            'content-security-policy': 'sandbox allow-scripts',
            'referrer-policy': 'no-referrer',
            'clear-site-data': '"storage"',
          },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const request = new NextRequest('https://nexus.example/app-html/some/module/console/index.html?token=jwt');

    const res = await GET(request, params);

    expect(res.headers.get('content-security-policy')).toBe('sandbox allow-scripts');
    expect(res.headers.get('referrer-policy')).toBe('no-referrer');
    expect(res.headers.get('clear-site-data')).toBeNull();
  });
});

describe('app-html proxy and streamed bodies', () => {
  it('streams a response as the upstream sends it, with its length', async () => {
    let push: (chunk: string) => void = () => {};
    let end: () => void = () => {};
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        push = (chunk) => controller.enqueue(new TextEncoder().encode(chunk));
        end = () => controller.close();
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(body, { status: 200, headers: { 'content-length': '10' } })),
    );
    const request = new NextRequest('https://nexus.example/app-html/some/module/console/export.csv?token=jwt');

    const res = await GET(request, params);
    expect(res.headers.get('content-length')).toBe('10');
    const reader = res.body!.getReader();
    push('first');
    // The first part arrives before the upstream finished: nothing is buffered.
    expect(new TextDecoder().decode((await reader.read()).value)).toBe('first');
    push('later');
    end();
    expect(new TextDecoder().decode((await reader.read()).value)).toBe('later');
    expect((await reader.read()).done).toBe(true);
  });

  it('drops the length of a body fetch has decompressed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response('decoded', { status: 200, headers: { 'content-length': '3', 'content-encoding': 'gzip' } }),
      ),
    );
    const request = new NextRequest('https://nexus.example/app-html/some/module/console/data.json?token=jwt');

    const res = await GET(request, params);

    expect(res.headers.get('content-length')).toBeNull();
    expect(await res.text()).toBe('decoded');
  });
});
