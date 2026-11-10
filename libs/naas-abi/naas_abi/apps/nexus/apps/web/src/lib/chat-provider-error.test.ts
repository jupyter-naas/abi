import { describe, expect, it } from 'vitest';

import { chatFailureText, chatResponseError, humanizeChatProviderError } from './chat-provider-error';
import { onViewRefusal } from './view-model';

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

const refusal = (detail: string, status = 403) =>
  new Response(JSON.stringify({ detail }), { status, headers: { 'Content-Type': 'application/json' } });

describe('a chat request that answers an error', () => {
  it("is the view's refusal as the server wrote it, and is announced", async () => {
    const heard: string[] = [];
    const off = onViewRefusal((message) => heard.push(message));
    const error = await chatResponseError(refusal('Read-only: you are viewing as Dave'));
    off();
    expect(error.message).toBe('Read-only: you are viewing as Dave');
    expect(heard).toEqual(['Read-only: you are viewing as Dave']);
    expect((await chatResponseError(refusal('Outside this view: you are viewing as Dave in Alpha'))).message).toBe(
      'Outside this view: you are viewing as Dave in Alpha',
    );
  });

  it('is the status for any other answer, announced to nobody', async () => {
    const heard: string[] = [];
    const off = onViewRefusal((message) => heard.push(message));
    expect((await chatResponseError(refusal('Not yours'))).message).toBe('API error: 403');
    expect((await chatResponseError(refusal('Read-only: x', 500))).message).toBe('API error: 500');
    off();
    expect(heard).toEqual([]);
  });
});

describe('chatFailureText', () => {
  it("shows a view's refusal as it is, with no advice about the provider", () => {
    expect(chatFailureText('Read-only: you are viewing as Dave')).toBe('🔒 Read-only: you are viewing as Dave');
  });

  it('keeps the advice for every other failure', () => {
    expect(chatFailureText('API error: 500')).toBe(
      '❌ Error: API error: 500\n\nPlease try again or check your provider settings.',
    );
  });
});
