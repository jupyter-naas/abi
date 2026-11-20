import { authFetch } from '@/stores/auth';

/** Appended to an assistant message while it streams. */
export const STREAMING_CARET = '▌';

/** How often, and how long, an open thread asks the server for a turn it is still answering. */
export const UNFINISHED_TURN_POLL_MS = 3000;
export const UNFINISHED_TURN_POLLS = 40;

/** `metadata.turn_status` of a reply the user's Stop ended. */
export const TURN_STOPPED = 'stopped';

type TurnMessage = { role: string; content: unknown; stopped?: boolean };

/**
 * True when the thread ends on an assistant reply not written yet: the caret
 * a stream leaves when its page goes away (a reload, a navigation), or the
 * empty row the server fills once the turn ends. The server runs a turn to
 * its end whether or not the page stays, so its copy is the one to show.
 * A stopped reply is final, empty or not.
 */
export function endsOnUnfinishedTurn(messages: ReadonlyArray<TurnMessage>): boolean {
  const last = messages[messages.length - 1];
  if (!last || last.role !== 'assistant' || typeof last.content !== 'string') return false;
  if (last.stopped) return false;
  const content = last.content.trimEnd();
  return content === '' || content.endsWith(STREAMING_CARET);
}

type Fetcher = (url: string, options?: RequestInit) => Promise<Response>;

/**
 * Stop the turn the server is running for a conversation: leaving its stream
 * does not (a reload must not), so Stop asks for it. Its reply keeps what it
 * had written, marked stopped. False when the server could not be asked.
 */
export async function stopTurn(conversationId: string, fetcher: Fetcher = authFetch): Promise<boolean> {
  try {
    const response = await fetcher(
      `/api/chat/conversations/${encodeURIComponent(conversationId)}/stop`,
      { method: 'POST' },
    );
    return response.ok;
  } catch {
    return false;
  }
}
