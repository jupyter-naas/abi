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
});
