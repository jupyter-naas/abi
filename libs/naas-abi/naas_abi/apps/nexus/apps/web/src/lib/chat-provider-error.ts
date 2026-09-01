const RATE_LIMIT_RE = /error code:\s*429|rate[- ]limited|temporarily rate-limited/i;
const RAW_PROVIDER_RE =
  /encountered an error while processing your request|error code:\s*\d+|provider returned error/i;

/** One-line chat error. Never show raw OpenRouter JSON in the bubble. */
export function humanizeChatProviderError(content: string): string {
  const raw = (content || '').trim();
  if (!raw) return raw;
  const looksDumped =
    RAW_PROVIDER_RE.test(raw) &&
    (raw.includes('{') || raw.includes("'error'") || raw.includes('"error"') || RATE_LIMIT_RE.test(raw));
  if (!looksDumped && !RATE_LIMIT_RE.test(raw)) return raw;
  if (RATE_LIMIT_RE.test(raw)) {
    return 'This model is rate limited. Pick another model in the agent menu and try again.';
  }
  return 'The model provider failed. Pick another model and try again.';
}
