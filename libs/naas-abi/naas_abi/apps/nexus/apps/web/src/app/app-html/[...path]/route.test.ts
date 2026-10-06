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
    const forwarded = new TextDecoder().decode(init.body as ArrayBuffer);
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
