import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const DEFAULT_API_URL = 'http://localhost:9879';
const API_SPEECH_PATH = '/api/speech';

/**
 * Proxies a text-to-speech request to the Python API speech endpoint.
 * Expects JSON: { text: string, voice?: string, model?: string }
 * Returns audio/mpeg bytes on success.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json().catch(() => null);
    if (!body || typeof body !== 'object' || typeof (body as { text?: unknown }).text !== 'string') {
      return NextResponse.json({ error: 'Missing text' }, { status: 400 });
    }

    const apiBase =
      process.env.NEXUS_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      DEFAULT_API_URL;

    const speechRes = await fetch(`${apiBase}${API_SPEECH_PATH}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!speechRes.ok) {
      const detail = await speechRes.text().catch(() => '');
      let payload: { error?: string; detail?: string } = {};
      try {
        payload = JSON.parse(detail) as { error?: string; detail?: string };
      } catch {
        payload = {};
      }
      return NextResponse.json(
        {
          error: payload.error || `Speech synthesis failed (${speechRes.status})`,
          detail: payload.detail || detail,
        },
        { status: speechRes.status }
      );
    }

    const audio = await speechRes.arrayBuffer();
    const contentType = speechRes.headers.get('content-type') || 'audio/mpeg';
    return new NextResponse(audio, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
