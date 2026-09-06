/**
 * The chat footer prints whatever `modelDisplayName` hands back, so an id it
 * cannot resolve is not a silent miss: the user reads a raw routing slug where
 * a model name belongs.
 */

import { describe, expect, it } from 'vitest';
import { modelDisplayName, type CatalogModel } from './models';

function model(over: Partial<CatalogModel> & { canonicalId: string }): CatalogModel {
  return {
    modelId: over.canonicalId,
    provider: 'openrouter',
    name: null,
    ...over,
  };
}

/** Trimmed from the live catalog, which spells one model three ways. */
const catalog: CatalogModel[] = [
  // OpenRouter rows carry the vendor prefix in `model_id` itself.
  model({
    canonicalId: 'claude-sonnet-4.5',
    modelId: 'anthropic/claude-sonnet-4.5',
    name: 'Sonnet 4.5',
  }),
  model({ canonicalId: 'gpt-5', modelId: 'openai/gpt-5', name: 'GPT-5' }),
  // Bedrock rows spell the same vendor with a dot, and Sonnet 5 is only here.
  model({
    canonicalId: 'claude-sonnet-5',
    modelId: 'anthropic.claude-sonnet-5',
    provider: 'bedrock',
    name: 'Claude Sonnet 5',
  }),
  model({ canonicalId: 'grok-4', modelId: 'grok-4', provider: 'xai', name: 'Grok 4' }),
  // A catalog row can arrive without a name at all.
  model({ canonicalId: 'gemini-2.5-flash', modelId: 'gemini-2.5-flash', provider: 'google' }),
];

describe('modelDisplayName', () => {
  it('has nothing to print without an id', () => {
    expect(modelDisplayName(catalog, null)).toBeNull();
    expect(modelDisplayName(catalog, '')).toBeNull();
  });

  it('resolves a canonical id', () => {
    expect(modelDisplayName(catalog, 'claude-sonnet-4.5')).toBe('Sonnet 4.5');
  });

  it('resolves a provider model id spelled the way the catalog spells it', () => {
    expect(modelDisplayName(catalog, 'anthropic/claude-sonnet-4.5')).toBe('Sonnet 4.5');
    expect(modelDisplayName(catalog, 'anthropic.claude-sonnet-5')).toBe('Claude Sonnet 5');
  });

  it('resolves a routing slug whose vendor prefix the catalog does not use', () => {
    // Slides run on OpenRouter, so the turn reports `anthropic/claude-sonnet-5`
    // while the only catalog row for that model is the Bedrock one. The name is
    // right there; exact-match lookup just could not reach it.
    expect(modelDisplayName(catalog, 'anthropic/claude-sonnet-5')).toBe('Claude Sonnet 5');
  });

  it('resolves a vendor prefix that was guessed wrong', () => {
    // Bare ids get prefixed by family guess, so anything not obviously Claude
    // comes back as `openai/<id>` whatever it really is.
    expect(modelDisplayName(catalog, 'openai/grok-4')).toBe('Grok 4');
  });

  it('falls back to the id when the catalog has no name for it', () => {
    expect(modelDisplayName(catalog, 'gemini-2.5-flash')).toBe('gemini-2.5-flash');
    expect(modelDisplayName(catalog, 'openai/gemini-2.5-flash')).toBe('openai/gemini-2.5-flash');
  });

  it('falls back to the id when the model is off catalog entirely', () => {
    expect(modelDisplayName(catalog, 'meta/llama-9')).toBe('meta/llama-9');
    expect(modelDisplayName([], 'anthropic/claude-sonnet-5')).toBe('anthropic/claude-sonnet-5');
  });

  it('does not read a bare slash as a model id', () => {
    expect(modelDisplayName(catalog, 'anthropic/')).toBe('anthropic/');
  });
});
