/**
 * Brand icons for AI models, from the LobeHub static icon set (MIT):
 * https://github.com/lobehub/lobe-icons — served from jsDelivr at a pinned
 * version. Bump deliberately, like any dependency.
 *
 * The icon is keyed by the model's brand, not its provider: a project can
 * serve every model through one provider (OpenRouter), and the brand is what
 * the user recognizes. `model_id` carries it as a prefix ("anthropic/…");
 * canonical ids sometimes do not ("claude-3-haiku"), so a keyword table
 * catches those.
 */
const LOBE_ICONS = 'https://cdn.jsdelivr.net/npm/@lobehub/icons-static-svg@1.104.0/icons';

export type BrandIcon = {
  url: string;
  /** Monochrome glyph (OpenAI, Grok…): rendered black; invert it on dark backgrounds. */
  mono: boolean;
};

const brand = (slug: string, mono = false): BrandIcon => ({
  url: `${LOBE_ICONS}/${slug}.svg`,
  mono,
});

/** Model-id prefixes — the brand the model is served as ("anthropic/claude-3-haiku"). */
const PREFIXES: Array<[RegExp, BrandIcon]> = [
  [/^anthropic\//, brand('claude-color')],
  [/^openai\//, brand('openai', true)],
  [/^google\//, brand('gemini-color')],
  [/^mistralai\//, brand('mistral-color')],
  [/^deepseek\//, brand('deepseek-color')],
  [/^qwen\//, brand('qwen-color')],
  [/^x-ai\//, brand('grok', true)],
  [/^meta-llama\//, brand('meta-color')],
  [/^perplexity\//, brand('perplexity-color')],
  [/^cohere\//, brand('cohere-color')],
];

/** Canonical-id keywords ("claude-3-haiku", "codestral-2508") when no prefix is around. */
const KEYWORDS: Array<[RegExp, BrandIcon]> = [
  [/claude/, brand('claude-color')],
  [/\b(gpt|codex|o[134])\b/, brand('openai', true)],
  [/gemini/, brand('gemini-color')],
  [/(mistral|codestral|devstral|ministral|magistral|pixtral)/, brand('mistral-color')],
  [/deepseek/, brand('deepseek-color')],
  [/qwen/, brand('qwen-color')],
  [/grok/, brand('grok', true)],
  [/llama/, brand('meta-color')],
  [/gemma/, brand('gemma-color')],
  [/(perplexity|sonar)/, brand('perplexity-color')],
];

/** The first brand icon matching any of the keys (model id, canonical id, name); null falls through. */
export function modelBrandIcon(...keys: Array<string | null | undefined>): BrandIcon | null {
  for (const key of keys) {
    if (!key) continue;
    for (const [pattern, icon] of PREFIXES) if (pattern.test(key)) return icon;
  }
  for (const key of keys) {
    if (!key) continue;
    for (const [pattern, icon] of KEYWORDS) if (pattern.test(key)) return icon;
  }
  return null;
}
