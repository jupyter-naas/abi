/** Appended to an assistant message while it streams. */
export const STREAMING_CARET = '▌';

/** How often, and how long, an open thread asks the server for a turn it is still answering. */
export const UNFINISHED_TURN_POLL_MS = 3000;
export const UNFINISHED_TURN_POLLS = 40;

type TurnMessage = { role: string; content: unknown };

/**
 * True when the thread ends on an assistant reply not written yet: the caret
 * a stream leaves when its page goes away (a reload, a navigation), or the
 * empty row the server fills once the turn ends. The server runs a turn to
 * its end whether or not the page stays, so its copy is the one to show.
 */
export function endsOnUnfinishedTurn(messages: ReadonlyArray<TurnMessage>): boolean {
  const last = messages[messages.length - 1];
  if (!last || last.role !== 'assistant' || typeof last.content !== 'string') return false;
  const content = last.content.trimEnd();
  return content === '' || content.endsWith(STREAMING_CARET);
}
