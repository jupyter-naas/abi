import { describe, expect, it } from 'vitest';

import { humanizeChatProviderError } from './chat-provider-error';

describe('humanizeChatProviderError', () => {
  it('rewrites a 429 JSON dump', () => {
    const dumped =
      "I'm sorry, I encountered an error while processing your request. Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'google/gemma-4-26b-a4b-it:free is temporarily rate-limited upstream.'}}}";
    expect(humanizeChatProviderError(dumped)).toBe(
      'This model is rate limited. Pick another model in the agent menu and try again.',
    );
  });

  it('leaves a normal assistant reply alone', () => {
    expect(humanizeChatProviderError('Updated the cover title and agenda.')).toBe(
      'Updated the cover title and agenda.',
    );
  });

  it('names a context-window 400 instead of asking to pick another model', () => {
    const dumped =
      "Error code: 400 - {'error': {'message': \"litellm.ContextWindowExceededError: This model's maximum context length is 262144 tokens.\"}}";
    expect(humanizeChatProviderError(dumped)).toBe(
      "This request exceeded the model's context window. Do not load whole files with embedded images, then try again.",
    );
  });
});
