import { describe, expect, it } from 'vitest';

import {
  autoDeckTitle,
  autoDocumentTitle,
  conversationTitleFromPrompt,
  deriveDocumentTitle,
  firstUserPrompt,
  isPlaceholderDeckTitle,
  isPlaceholderDocumentTitle,
  shouldAutoTitleDocument,
} from './office-auto-title';

describe('conversationTitleFromPrompt', () => {
  it('clips at 50 characters like Chat', () => {
    const short = 'Write an executive memo on two firms';
    expect(conversationTitleFromPrompt(short)).toBe(short);
    expect(conversationTitleFromPrompt('A'.repeat(51))).toBe(`${'A'.repeat(50)}...`);
  });
});

describe('firstUserPrompt', () => {
  it('keeps the original brief on a follow-up', () => {
    expect(
      firstUserPrompt('continue', [
        { role: 'user', content: 'Write an executive memo on two firms' },
        { role: 'assistant', content: 'Working on it.' },
        { role: 'user', content: 'continue' },
      ]),
    ).toBe('Write an executive memo on two firms');
  });
});

describe('placeholder titles', () => {
  it('treats Untitled and untitled slugs as placeholders', () => {
    expect(isPlaceholderDocumentTitle('Untitled document')).toBe(true);
    expect(isPlaceholderDocumentTitle('untitled-mty54m03')).toBe(true);
    expect(isPlaceholderDocumentTitle('Already named')).toBe(false);
    expect(isPlaceholderDeckTitle('Untitled presentation')).toBe(true);
    expect(shouldAutoTitleDocument('Untitled document', 'untitled-abc')).toBe(true);
    expect(shouldAutoTitleDocument('Already named', 'untitled-abc')).toBe(false);
  });
});

describe('auto office titles', () => {
  it('extracts the topic from an executive memo brief', () => {
    expect(deriveDocumentTitle('Write an executive memo on two audit firms')).toBe(
      'Two audit firms',
    );
  });

  it('falls back to the Chat clip when the brief is not a document request', () => {
    const brief = 'What is going on in France right now?';
    expect(deriveDocumentTitle(brief)).toBe('');
    expect(autoDocumentTitle(brief)).toBe(brief);
    expect(autoDeckTitle(brief)).toBe(brief);
  });
});
