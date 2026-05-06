import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

function toBase64(data: ArrayBuffer): string {
  return Buffer.from(data).toString('base64');
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const url = searchParams.get('url');

  if (!url) {
    return NextResponse.json({ error: 'Missing url' }, { status: 400 });
  }

  try {
    const res = await fetch(url, { cache: 'force-cache' });
    if (!res.ok) {
      return NextResponse.json({ error: `Upstream error (${res.status})` }, { status: 502 });
    }

    const contentType = res.headers.get('content-type') || 'application/octet-stream';
    const arrayBuffer = await res.arrayBuffer();
    const base64 = toBase64(arrayBuffer);
    const dataUri = `data:${contentType};base64,${base64}`;

    return NextResponse.json({ dataUri });
  } catch (err) {
    return NextResponse.json({ error: 'Failed to fetch image' }, { status: 500 });
  }
}

