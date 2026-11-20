import { describe, expect, it } from 'vitest';

import { modelBrandIcon } from './model-icons';

describe('modelBrandIcon', () => {
  it('keys on the model id prefix, not the provider', () => {
    expect(modelBrandIcon('anthropic/claude-3-haiku')?.url).toContain('claude-color');
    expect(modelBrandIcon('mistralai/codestral-2508')?.url).toContain('mistral-color');
    expect(modelBrandIcon('google/gemini-3.1-pro-preview')?.url).toContain('gemini-color');
  });

  it('falls back to canonical-id keywords when there is no prefix', () => {
    expect(modelBrandIcon(null, 'claude-3-haiku')?.url).toContain('claude-color');
    expect(modelBrandIcon(null, 'devstral-2-2512')?.url).toContain('mistral-color');
    expect(modelBrandIcon(null, 'qwen3-8b')?.url).toContain('qwen-color');
    expect(modelBrandIcon(null, 'sonar-pro')?.url).toContain('perplexity-color');
  });

  it('marks monochrome brands so callers can invert them on dark backgrounds', () => {
    expect(modelBrandIcon('openai/o3')?.mono).toBe(true);
    expect(modelBrandIcon(null, 'grok-4')?.mono).toBe(true);
    expect(modelBrandIcon('anthropic/claude-3-haiku')?.mono).toBe(false);
  });

  it('returns null for unknown brands, leaving the caller its fallback', () => {
    expect(modelBrandIcon('zettafox/whatever')).toBeNull();
    expect(modelBrandIcon(null, undefined, '')).toBeNull();
  });
});
