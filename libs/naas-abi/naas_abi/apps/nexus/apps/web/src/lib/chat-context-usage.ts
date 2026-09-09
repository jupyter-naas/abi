/**
 * Composer context-window estimate for Nexus chat.
 *
 * Honest numbers only: last-request prompt_tokens when the stream sends them,
 * plus a client-side estimate of the draft, attached images, and visible
 * transcript. System prompt / tools / skills are not measured here unless they
 * already sit in the transcript (for example a tool output).
 */

export const CHARS_PER_TOKEN_ESTIMATE = 4;

/** Cap each stored tool dump in the client estimate. Matches Agent.py. */
export const ESTIMATE_TOOL_OUTPUT_CHARS = 8_000;

/** Product default: Qwen 3.8 on GAIA. Used only when the catalog has no window. */
export const QWEN_38_CONTEXT_WINDOW = 262144;

export const CONTEXT_USAGE_WARN = 0.7;
export const CONTEXT_USAGE_DANGER = 0.9;

const DATA_URL_RE = /data:(image|application)\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+/gi;
const DECK_HTML_RE = /deck\.html|<!DOCTYPE\s+html|<html[\s>]/i;

const KNOWN_WINDOWS: Array<{ match: RegExp; tokens: number }> = [
  { match: /qwen[-/.]?3[.-]?[68]/i, tokens: QWEN_38_CONTEXT_WINDOW },
  { match: /Qwen\/Qwen3/i, tokens: QWEN_38_CONTEXT_WINDOW },
];

export type ContextUsageTone = 'calm' | 'warning' | 'danger';

export type ContextUsageBucketId =
  | 'last_request'
  | 'conversation'
  | 'system'
  | 'draft'
  | 'attachments'
  | 'output_reserve';

export type ContextUsageBucket = {
  id: ContextUsageBucketId;
  label: string;
  tokens: number;
  estimated: boolean;
};

export type ContextWindowSource = 'catalog' | 'known' | 'assumed';

export type StreamTokenUsage = {
  promptTokens: number;
  completionTokens: number | null;
};

export type ContextUsageInput = {
  messages: Array<{
    content?: string;
    images?: string[];
    toolCalls?: Array<{ input?: string; output?: string }>;
  }>;
  draft: string;
  attachedImages: string[];
  attachedFileNames: string[];
  slidesPath: string | null;
  lastPromptTokens: number | null;
  contextWindow: number;
  windowSource: ContextWindowSource;
  systemPrompt: string | null;
  reservedOutputTokens: number | null;
};

export type ContextUsageSnapshot = {
  usedTokens: number;
  windowTokens: number;
  percent: number;
  tone: ContextUsageTone;
  buckets: ContextUsageBucket[];
  hasMeasuredUsage: boolean;
  windowSource: ContextWindowSource;
  /** Button title only. Not shown in the popover. */
  tooltip: string;
  /** One line, and only when reserve would change calm/warning/danger. */
  reserveFootnote: string | null;
};

export function estimateTokensFromText(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / CHARS_PER_TOKEN_ESTIMATE);
}

export function findEmbeddedDataUrls(text: string): { count: number; chars: number } {
  if (!text) return { count: 0, chars: 0 };
  let count = 0;
  let chars = 0;
  const re = new RegExp(DATA_URL_RE.source, DATA_URL_RE.flags);
  for (const match of text.matchAll(re)) {
    count += 1;
    chars += match[0].length;
  }
  return { count, chars };
}

export function looksLikeHeavyDeckPayload(text: string): boolean {
  if (!text) return false;
  const urls = findEmbeddedDataUrls(text);
  if (urls.count >= 3) return true;
  if (urls.count >= 1 && DECK_HTML_RE.test(text)) return true;
  if (urls.chars >= 50_000) return true;
  return false;
}

export function contextUsageTone(percent: number): ContextUsageTone {
  if (percent >= CONTEXT_USAGE_DANGER * 100) return 'danger';
  if (percent >= CONTEXT_USAGE_WARN * 100) return 'warning';
  return 'calm';
}

export function formatCompactTokens(n: number): string {
  const abs = Math.max(0, Math.round(n));
  if (abs < 1000) return String(abs);
  if (abs < 1_000_000) {
    const k = abs / 1000;
    return Number.isInteger(k) ? `${k}K` : `${k.toFixed(1)}K`;
  }
  return `${(abs / 1_000_000).toFixed(1)}M`;
}

export function asFiniteTokenCount(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) {
    return Math.round(value);
  }
  if (typeof value === 'string' && value.trim()) {
    const n = Number(value);
    if (Number.isFinite(n) && n >= 0) return Math.round(n);
  }
  return null;
}

function readUsageRecord(value: unknown): StreamTokenUsage | null {
  if (!value || typeof value !== 'object') return null;
  const rec = value as Record<string, unknown>;
  const prompt =
    asFiniteTokenCount(rec.prompt_tokens) ??
    asFiniteTokenCount(rec.input_tokens) ??
    asFiniteTokenCount(rec.promptTokens);
  if (prompt == null) return null;
  const completion =
    asFiniteTokenCount(rec.completion_tokens) ??
    asFiniteTokenCount(rec.output_tokens) ??
    asFiniteTokenCount(rec.completionTokens);
  return { promptTokens: prompt, completionTokens: completion };
}

/** Pull prompt_tokens off an SSE frame if the API ever sends them. */
export function parseStreamTokenUsage(parsed: unknown): StreamTokenUsage | null {
  if (!parsed || typeof parsed !== 'object') return null;
  const rec = parsed as Record<string, unknown>;
  return (
    readUsageRecord(rec.token_usage) ??
    readUsageRecord(rec.usage) ??
    readUsageRecord(rec)
  );
}

function findCatalogWindow(
  modelId: string | null,
  catalog: Array<{ modelId: string; canonicalId: string; contextWindow?: number | null }>,
): number | null {
  if (!modelId) return null;
  const exact = catalog.find((m) => m.modelId === modelId || m.canonicalId === modelId);
  if (exact?.contextWindow && exact.contextWindow > 0) return exact.contextWindow;
  const bare = modelId.includes('/') ? modelId.slice(modelId.lastIndexOf('/') + 1) : '';
  if (!bare) return null;
  const routed = catalog.find((m) => m.canonicalId === bare || m.modelId === bare);
  if (routed?.contextWindow && routed.contextWindow > 0) return routed.contextWindow;
  return null;
}

export function resolveContextWindow(
  modelId: string | null,
  catalog: Array<{ modelId: string; canonicalId: string; contextWindow?: number | null }>,
): { tokens: number; source: ContextWindowSource } {
  const fromCatalog = findCatalogWindow(modelId, catalog);
  if (fromCatalog) return { tokens: fromCatalog, source: 'catalog' };
  if (modelId) {
    for (const row of KNOWN_WINDOWS) {
      if (row.match.test(modelId)) return { tokens: row.tokens, source: 'known' };
    }
  }
  return { tokens: QWEN_38_CONTEXT_WINDOW, source: 'assumed' };
}

/** Qwen 3.8 max_tokens after the overflow fix. Other models: unknown, omit. */
export function reservedOutputTokensForModel(modelId: string | null): number | null {
  if (!modelId) return null;
  if (/qwen[-/.]?3[.-]?[68]/i.test(modelId) || /Qwen\/Qwen3/i.test(modelId)) {
    return 16384;
  }
  return null;
}

function clipForEstimate(text: string): string {
  if (text.length <= ESTIMATE_TOOL_OUTPUT_CHARS) return text;
  return text.slice(0, ESTIMATE_TOOL_OUTPUT_CHARS);
}

function collectTranscriptText(
  messages: ContextUsageInput['messages'],
): string {
  const parts: string[] = [];
  for (const message of messages) {
    if (message.content) parts.push(message.content);
    for (const image of message.images ?? []) {
      if (image) parts.push(image);
    }
    for (const tool of message.toolCalls ?? []) {
      if (tool.input) parts.push(clipForEstimate(tool.input));
      if (tool.output) parts.push(clipForEstimate(tool.output));
    }
  }
  return parts.join('\n');
}

function transcriptLooksHeavy(messages: ContextUsageInput['messages']): boolean {
  for (const message of messages) {
    if (message.content && looksLikeHeavyDeckPayload(message.content)) return true;
    for (const tool of message.toolCalls ?? []) {
      if (tool.output && looksLikeHeavyDeckPayload(tool.output)) return true;
    }
  }
  return false;
}

export function buildContextUsage(input: ContextUsageInput): ContextUsageSnapshot {
  const transcript = collectTranscriptText(input.messages);
  const draftTokens = estimateTokensFromText(input.draft);
  const attachmentText = input.attachedImages.join('');
  const attachmentTokens = estimateTokensFromText(attachmentText);
  const conversationTokens = estimateTokensFromText(transcript);
  const systemTokens = input.systemPrompt ? estimateTokensFromText(input.systemPrompt) : 0;
  const measured = input.lastPromptTokens != null && input.lastPromptTokens > 0;

  const buckets: ContextUsageBucket[] = [];
  if (measured) {
    buckets.push({
      id: 'last_request',
      label: 'Last request',
      tokens: input.lastPromptTokens as number,
      estimated: false,
    });
  } else {
    if (systemTokens > 0) {
      buckets.push({
        id: 'system',
        label: 'System prompt',
        tokens: systemTokens,
        estimated: true,
      });
    }
    if (conversationTokens > 0) {
      buckets.push({
        id: 'conversation',
        label: 'Conversation',
        tokens: conversationTokens,
        estimated: true,
      });
    }
  }
  if (draftTokens > 0) {
    buckets.push({
      id: 'draft',
      label: 'Draft',
      tokens: draftTokens,
      estimated: true,
    });
  }
  if (attachmentTokens > 0) {
    buckets.push({
      id: 'attachments',
      label: 'Attachments',
      tokens: attachmentTokens,
      estimated: true,
    });
  }

  const usedTokens = buckets.reduce((sum, bucket) => sum + bucket.tokens, 0);
  const windowTokens = input.contextWindow > 0 ? input.contextWindow : QWEN_38_CONTEXT_WINDOW;
  const percent = windowTokens > 0 ? Math.min(999, (usedTokens / windowTokens) * 100) : 0;
  const tone = contextUsageTone(percent);
  const reserve = input.reservedOutputTokens && input.reservedOutputTokens > 0
    ? input.reservedOutputTokens
    : 0;
  const toneWithReserve =
    reserve > 0 && windowTokens > 0
      ? contextUsageTone(Math.min(999, ((usedTokens + reserve) / windowTokens) * 100))
      : tone;
  const reserveFootnote =
    reserve > 0 && toneWithReserve !== tone
      ? `+~${formatCompactTokens(reserve)} output reserve`
      : null;

  const tooltipParts = [`Context usage ${Math.round(percent)}%`];
  if (transcriptLooksHeavy(input.messages)) {
    tooltipParts.push('Conversation includes a full deck.html with embedded images.');
  }

  return {
    usedTokens,
    windowTokens,
    percent,
    tone,
    buckets,
    hasMeasuredUsage: measured,
    windowSource: input.windowSource,
    tooltip: tooltipParts.join('. '),
    reserveFootnote,
  };
}
