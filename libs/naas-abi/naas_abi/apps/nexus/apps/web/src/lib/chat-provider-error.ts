import { announceViewRefusal, isViewRefusal, viewRefusalMessage } from './view-model';

const RATE_LIMIT_RE = /error code:\s*429|rate[- ]limited|temporarily rate-limited/i;
const CONTEXT_WINDOW_RE =
  /contextwindowexceeded|context window|maximum context length/i;
const RAW_PROVIDER_RE =
  /encountered an error while processing your request|error code:\s*\d+|provider returned error/i;

/** One-line chat error. Never show raw OpenRouter JSON in the bubble. */
export function humanizeChatProviderError(content: string): string {
  const raw = (content || '').trim();
  if (!raw) return raw;
  if (CONTEXT_WINDOW_RE.test(raw)) {
    return (
      "This request exceeded the model's context window. " +
      'Do not load whole files with embedded images, then try again.'
    );
  }
  const looksDumped =
    RAW_PROVIDER_RE.test(raw) &&
    (raw.includes('{') || raw.includes("'error'") || raw.includes('"error"') || RATE_LIMIT_RE.test(raw));
  if (!looksDumped && !RATE_LIMIT_RE.test(raw)) return raw;
  if (RATE_LIMIT_RE.test(raw)) {
    return 'This model is rate limited. Pick another model in the agent menu and try again.';
  }
  return 'The model provider failed. Pick another model and try again.';
}

/**
 * The failure of a chat request the server answered with an error: the message of the view's refusal
 * ("Read-only: …", "Outside this view: …"), which the banner announces as it does for every other call
 * (the chat sends with `fetch`, not `authFetch`), else the status.
 */
export async function chatResponseError(response: Response): Promise<Error> {
  const refusal = await viewRefusalMessage(response);
  if (refusal) {
    announceViewRefusal(refusal);
    return new Error(refusal);
  }
  return new Error(`API error: ${response.status}`);
}

/** What the bubble says when a request failed: a view's refusal as the server wrote it, any other failure with
 *  the advice to try again. */
export function chatFailureText(message: string): string {
  if (isViewRefusal(message)) return `🔒 ${message}`;
  return `❌ Error: ${message}\n\nPlease try again or check your provider settings.`;
}
