import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const OPENAI_TRANSCRIBE_URL = 'https://api.openai.com/v1/audio/transcriptions';
const TRANSCRIBE_MODEL = 'gpt-4o-mini-transcribe';

/**
 * Proxies an uploaded audio blob to OpenAI's transcription API.
 * Expects multipart/form-data with an `audio` file field.
 * Optional `apiKey` form field is accepted as a fallback when the
 * OPENAI_API_KEY env var is not configured on the server.
 */
export async function POST(request: NextRequest) {
  try {
    const form = await request.formData();
    const audio = form.get('audio');
    if (!(audio instanceof Blob)) {
      return NextResponse.json({ error: 'Missing audio file' }, { status: 400 });
    }

    const bodyApiKey = form.get('apiKey');
    const apiKey =
      (typeof bodyApiKey === 'string' && bodyApiKey.trim()) ||
      process.env.OPENAI_API_KEY ||
      '';

    if (!apiKey) {
      return NextResponse.json(
        { error: 'OPENAI_API_KEY not configured on the server' },
        { status: 500 }
      );
    }

    const filename =
      (audio instanceof File && audio.name) ||
      `recording-${Date.now()}.webm`;

    const openaiForm = new FormData();
    openaiForm.append('model', TRANSCRIBE_MODEL);
    openaiForm.append('file', audio, filename);

    const openaiRes = await fetch(OPENAI_TRANSCRIBE_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}` },
      body: openaiForm,
    });

    if (!openaiRes.ok) {
      const detail = await openaiRes.text().catch(() => '');
      return NextResponse.json(
        { error: `OpenAI transcription failed (${openaiRes.status})`, detail },
        { status: openaiRes.status }
      );
    }

    const data = (await openaiRes.json()) as { text?: string };
    return NextResponse.json({ text: data.text ?? '' });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
