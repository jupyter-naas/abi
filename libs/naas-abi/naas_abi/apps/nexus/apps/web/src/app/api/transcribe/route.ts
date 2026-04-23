import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const DEFAULT_API_URL = 'http://localhost:9879';
const API_TRANSCRIBE_PATH = '/api/transcribe';

/**
 * Proxies an uploaded audio blob to the Python API transcription endpoint.
 * Expects multipart/form-data with an `audio` file field.
 * Optional `apiKey` form field is forwarded for per-request overrides.
 * Optional `conversation_id` form field is preserved and echoed back
 * so the caller can associate the transcript with an ongoing chat.
 */
export async function POST(request: NextRequest) {
  try {
    const incomingForm = await request.formData();
    const audio = incomingForm.get('audio');
    if (!(audio instanceof Blob)) {
      return NextResponse.json({ error: 'Missing audio file' }, { status: 400 });
    }

    const outgoingForm = new FormData();
    const filename =
      (audio instanceof File && audio.name) ||
      `recording-${Date.now()}.webm`;
    outgoingForm.append('audio', audio, filename);

    const bodyApiKey = incomingForm.get('apiKey');
    if (typeof bodyApiKey === 'string' && bodyApiKey.trim()) {
      outgoingForm.append('apiKey', bodyApiKey.trim());
    }

    const bodyConversationId = incomingForm.get('conversation_id');
    const conversationId =
      typeof bodyConversationId === 'string' && bodyConversationId.trim()
        ? bodyConversationId.trim()
        : null;
    if (conversationId) {
      outgoingForm.append('conversation_id', conversationId);
    }

    const apiBase =
      process.env.NEXUS_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      DEFAULT_API_URL;

    const transcribeRes = await fetch(`${apiBase}${API_TRANSCRIBE_PATH}`, {
      method: 'POST',
      body: outgoingForm,
    });

    if (!transcribeRes.ok) {
      const detail = await transcribeRes.text().catch(() => '');
      let payload: { error?: string; detail?: string; conversation_id?: string } = {};
      try {
        payload = JSON.parse(detail) as {
          error?: string;
          detail?: string;
          conversation_id?: string;
        };
      } catch {
        payload = {};
      }

      return NextResponse.json(
        {
          error: payload.error || `Transcription failed (${transcribeRes.status})`,
          detail: payload.detail || detail,
          conversation_id: payload.conversation_id ?? conversationId,
        },
        { status: transcribeRes.status }
      );
    }

    const data = (await transcribeRes.json()) as {
      text?: string;
      conversation_id?: string | null;
    };
    return NextResponse.json({
      text: data.text ?? '',
      conversation_id: data.conversation_id ?? conversationId,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
