/**
 * Streaming proxy for /api/analytics/chats/{id}/export.
 *
 * The upstream returns a binary file (text/plain, application/json, or
 * text/markdown) with a Content-Disposition header. We forward the body and
 * its headers unchanged so the browser sees the same download response it
 * would get from the chat-interface export.
 */

export const dynamic = 'force-dynamic';

const UPSTREAM =
  process.env.NEXUS_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:9879';

export async function GET(req: Request, { params }: { params: { id: string } }) {
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${UPSTREAM}/api/analytics/chats/${encodeURIComponent(params.id)}/export${
    qs ? `?${qs}` : ''
  }`;

  try {
    const res = await fetch(target, { cache: 'no-store' });
    const headers = new Headers();
    const contentType = res.headers.get('content-type');
    const disposition = res.headers.get('content-disposition');
    if (contentType) headers.set('content-type', contentType);
    if (disposition) headers.set('content-disposition', disposition);
    return new Response(res.body, { status: res.status, headers });
  } catch {
    return Response.json({ error: 'upstream unreachable' }, { status: 502 });
  }
}
