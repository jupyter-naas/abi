import { NextResponse } from 'next/server';
import { readLocalImage } from '@/lib/local-image-file';

export const runtime = 'nodejs';

function toBase64(data: ArrayBuffer | Buffer): string {
  return Buffer.from(data).toString('base64');
}

function asImageResponse(bytes: Buffer, contentType: string, raw: boolean) {
  if (raw) {
    return new NextResponse(new Uint8Array(bytes), {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600',
      },
    });
  }
  return NextResponse.json({ dataUri: `data:${contentType};base64,${toBase64(bytes)}` });
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const url = searchParams.get('url');
  const raw = searchParams.get('raw') === '1';

  if (!url) {
    return NextResponse.json({ error: 'Missing url' }, { status: 400 });
  }

  const local = readLocalImage(url);
  if (local) {
    return asImageResponse(local.bytes, local.contentType, raw);
  }

  if (url.startsWith('file://') || !/^https?:\/\//i.test(url)) {
    return NextResponse.json({ error: 'Image not found' }, { status: 404 });
  }

  try {
    const res = await fetch(url, { cache: 'force-cache' });
    if (!res.ok) {
      return NextResponse.json({ error: `Upstream error (${res.status})` }, { status: 502 });
    }

    const contentType = res.headers.get('content-type') || 'application/octet-stream';
    const arrayBuffer = await res.arrayBuffer();
    return asImageResponse(Buffer.from(arrayBuffer), contentType, raw);
  } catch {
    return NextResponse.json({ error: 'Failed to fetch image' }, { status: 500 });
  }
}
