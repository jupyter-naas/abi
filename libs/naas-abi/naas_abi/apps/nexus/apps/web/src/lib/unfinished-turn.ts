import { authFetch } from '@/stores/auth';

/** Appended to an assistant message while it streams. */
export const STREAMING_CARET = '▌';

/** How often, and how long, an open thread asks the server for a turn it is still answering. */
export const UNFINISHED_TURN_POLL_MS = 3000;
export const UNFINISHED_TURN_POLLS = 40;

/** `metadata.turn_status` of a reply the server is still writing, and of one the user's Stop ended. */
export const TURN_STREAMING = 'streaming';
export const TURN_STOPPED = 'stopped';

/**
 * A reply's content as the server saved it. One it is still writing holds
 * what it has written so far and ends on the caret, as a live stream does: the
 * thread shows it streaming and asks for it again.
 */
export function serverReplyContent(content: string, turnStatus: unknown): string {
  return turnStatus === TURN_STREAMING ? `${content}${STREAMING_CARET}` : content;
}

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

/**
 * Ask for the server's copy of an unfinished turn (`load`) now, then every
 * UNFINISHED_TURN_POLL_MS until the returned function is called. A turn still
 * writing (the thread's last content, `lastContent`, changes) is asked for as
 * long as it writes; after UNFINISHED_TURN_POLLS asks with no change it is
 * given up (its server may have died with it).
 */
export function watchUnfinishedTurn(load: () => void, lastContent: () => unknown): () => void {
  let polls = 0;
  let seen = lastContent();
  const poll = () => {
    polls += 1;
    load();
  };
  poll();
  const timer = setInterval(() => {
    const now = lastContent();
    if (now !== seen) {
      seen = now;
      polls = 0;
    }
    if (polls >= UNFINISHED_TURN_POLLS) clearInterval(timer);
    else poll();
  }, UNFINISHED_TURN_POLL_MS);
  return () => clearInterval(timer);
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
