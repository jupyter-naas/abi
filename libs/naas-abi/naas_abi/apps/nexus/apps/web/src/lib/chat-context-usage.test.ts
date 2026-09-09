import { describe, expect, it } from 'vitest';

import {
  ESTIMATE_TOOL_OUTPUT_CHARS,
  QWEN_38_CONTEXT_WINDOW,
  buildContextUsage,
  contextUsageTone,
  estimateTokensFromText,
  findEmbeddedDataUrls,
  formatCompactTokens,
  looksLikeHeavyDeckPayload,
  parseStreamTokenUsage,
  reservedOutputTokensForModel,
  resolveContextWindow,
} from './chat-context-usage';

describe('estimateTokensFromText', () => {
  it('uses ~4 characters per token', () => {
    expect(estimateTokensFromText('abcd')).toBe(1);
    expect(estimateTokensFromText('abcdefgh')).toBe(2);
  });

  it('returns 0 for empty text', () => {
    expect(estimateTokensFromText('')).toBe(0);
  });
});

describe('formatCompactTokens', () => {
  it('keeps small counts as integers', () => {
    expect(formatCompactTokens(42)).toBe('42');
  });

  it('formats thousands like Cursor', () => {
    expect(formatCompactTokens(162145)).toBe('162.1K');
    expect(formatCompactTokens(262144)).toBe('262.1K');
  });
});

describe('contextUsageTone', () => {
  it('is calm below 70%, warning through 90%, danger above', () => {
    expect(contextUsageTone(0)).toBe('calm');
    expect(contextUsageTone(69.9)).toBe('calm');
    expect(contextUsageTone(70)).toBe('warning');
    expect(contextUsageTone(90)).toBe('danger');
    expect(contextUsageTone(101)).toBe('danger');
  });
});

describe('data-URL / deck detection', () => {
  const dataUrl = `data:image/png;base64,${'A'.repeat(80)}`;

  it('counts embedded data URLs', () => {
    const found = findEmbeddedDataUrls(`<img src="${dataUrl}"><img src="${dataUrl}">`);
    expect(found.count).toBe(2);
    expect(found.chars).toBeGreaterThan(100);
  });

  it('flags a deck.html with embedded images', () => {
    expect(looksLikeHeavyDeckPayload(`<!DOCTYPE html>${dataUrl}`)).toBe(true);
    expect(looksLikeHeavyDeckPayload('hello')).toBe(false);
  });
});

describe('parseStreamTokenUsage', () => {
  it('reads token_usage.prompt_tokens', () => {
    expect(parseStreamTokenUsage({ token_usage: { prompt_tokens: 162145 } })).toEqual({
      promptTokens: 162145,
      completionTokens: null,
    });
  });

  it('reads usage.prompt_tokens and completion_tokens', () => {
    expect(
      parseStreamTokenUsage({ usage: { prompt_tokens: 100, completion_tokens: 20 } }),
    ).toEqual({ promptTokens: 100, completionTokens: 20 });
  });

  it('returns null when the frame has no usage', () => {
    expect(parseStreamTokenUsage({ content: 'hi' })).toBeNull();
    expect(parseStreamTokenUsage(null)).toBeNull();
  });
});

describe('resolveContextWindow', () => {
  it('prefers the catalog', () => {
    expect(
      resolveContextWindow('qwen-3.8', [
        { modelId: 'Qwen/Qwen3.8-27B-FP8-HARNESS', canonicalId: 'qwen-3.8', contextWindow: 200000 },
      ]),
    ).toEqual({ tokens: 200000, source: 'catalog' });
  });

  it('falls back to the known Qwen 3.8 window', () => {
    expect(resolveContextWindow('qwen-3.8', [])).toEqual({
      tokens: QWEN_38_CONTEXT_WINDOW,
      source: 'known',
    });
  });

  it('assumes the Qwen 3.8 window when the model is unknown', () => {
    expect(resolveContextWindow('mystery-model', [])).toEqual({
      tokens: QWEN_38_CONTEXT_WINDOW,
      source: 'assumed',
    });
  });
});

describe('reservedOutputTokensForModel', () => {
  it('returns 16384 for Qwen 3.8', () => {
    expect(reservedOutputTokensForModel('qwen-3.8')).toBe(16384);
    expect(reservedOutputTokensForModel('Qwen/Qwen3.8-27B-FP8-HARNESS')).toBe(16384);
  });

  it('returns null for unknown models', () => {
    expect(reservedOutputTokensForModel('gpt-4o')).toBeNull();
  });
});

describe('buildContextUsage', () => {
  it('uses last prompt_tokens as the conversation baseline and adds the draft', () => {
    const snap = buildContextUsage({
      messages: [{ content: 'old transcript that should not be double counted' }],
      draft: 'abcd',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: null,
      lastPromptTokens: 162145,
      contextWindow: 262144,
      windowSource: 'catalog',
      systemPrompt: 'you are bob',
      reservedOutputTokens: 16384,
    });
    expect(snap.hasMeasuredUsage).toBe(true);
    expect(snap.buckets.find((b) => b.id === 'last_request')).toEqual({
      id: 'last_request',
      label: 'Last request',
      tokens: 162145,
      estimated: false,
    });
    expect(snap.buckets.find((b) => b.id === 'conversation')).toBeUndefined();
    expect(snap.buckets.find((b) => b.id === 'draft')?.tokens).toBe(1);
    expect(snap.buckets.find((b) => b.id === 'output_reserve')).toBeUndefined();
    expect(snap.usedTokens).toBe(162145 + 1);
    expect(snap.tone).toBe('calm');
    expect(snap.reserveFootnote).toBeNull();
  });

  it('keeps reserve off the ring and footnotes only when it would change tone', () => {
    const empty = buildContextUsage({
      messages: [],
      draft: '',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: null,
      lastPromptTokens: null,
      contextWindow: 262144,
      windowSource: 'catalog',
      systemPrompt: 'you are bob',
      reservedOutputTokens: 16384,
    });
    expect(empty.buckets.find((b) => b.id === 'output_reserve')).toBeUndefined();
    expect(empty.tone).toBe('calm');
    expect(empty.reserveFootnote).toBeNull();

    const nearWarn = buildContextUsage({
      messages: [],
      draft: '',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: null,
      lastPromptTokens: 180000,
      contextWindow: 262144,
      windowSource: 'catalog',
      systemPrompt: null,
      reservedOutputTokens: 16384,
    });
    expect(nearWarn.usedTokens).toBe(180000);
    expect(nearWarn.tone).toBe('calm');
    expect(nearWarn.reserveFootnote).toBe('+~16.4K output reserve');
  });

  it('estimates conversation when the last request was not reported', () => {
    const snap = buildContextUsage({
      messages: [{ content: 'abcdefgh' }],
      draft: '',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: null,
      lastPromptTokens: null,
      contextWindow: 262144,
      windowSource: 'catalog',
      systemPrompt: null,
      reservedOutputTokens: null,
    });
    expect(snap.hasMeasuredUsage).toBe(false);
    expect(snap.buckets[0]).toMatchObject({ id: 'conversation', tokens: 2, estimated: true });
    expect(snap.tooltip).toMatch(/^Context usage /);
  });

  it('calls out a data-URL heavy deck in the transcript', () => {
    const dataUrl = `data:image/png;base64,${'A'.repeat(80)}`;
    const snap = buildContextUsage({
      messages: [
        {
          content: 'ok',
          toolCalls: [{ output: `<!DOCTYPE html>${dataUrl}${dataUrl}${dataUrl}` }],
        },
      ],
      draft: '',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: 'slides/ws-1/untitled/deck.html',
      lastPromptTokens: null,
      contextWindow: 262144,
      windowSource: 'known',
      systemPrompt: null,
      reservedOutputTokens: null,
    });
    expect(snap.tooltip).toContain('Conversation includes a full deck.html with embedded images.');
  });

  it('does not treat a stored 158K tool dump as 40K prompt tokens', () => {
    const dump = `<!DOCTYPE html>${'A'.repeat(158_000)}`;
    const snap = buildContextUsage({
      messages: [{ content: 'ok', toolCalls: [{ output: dump }] }],
      draft: '',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: null,
      lastPromptTokens: null,
      contextWindow: 262144,
      windowSource: 'catalog',
      systemPrompt: null,
      reservedOutputTokens: null,
    });
    const conversation = snap.buckets.find((b) => b.id === 'conversation');
    expect(conversation?.tokens).toBeLessThanOrEqual(
      Math.ceil(ESTIMATE_TOOL_OUTPUT_CHARS / 4) + 1,
    );
    expect(snap.usedTokens).toBeLessThan(10_000);
  });

  it('does not put an unread open deck into the popover', () => {
    const snap = buildContextUsage({
      messages: [],
      draft: '',
      attachedImages: [],
      attachedFileNames: [],
      slidesPath: 'slides/ws-1/untitled/deck.html',
      lastPromptTokens: null,
      contextWindow: 262144,
      windowSource: 'catalog',
      systemPrompt: null,
      reservedOutputTokens: null,
    });
    expect(snap.tooltip).not.toContain('deck.html');
    expect(snap.tooltip).not.toContain('not counted');
  });
});
