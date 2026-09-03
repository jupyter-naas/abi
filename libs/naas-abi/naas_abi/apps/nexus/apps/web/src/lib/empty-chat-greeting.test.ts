import { describe, expect, it } from 'vitest';

import {
  DEFAULT_COMPOSER_PLACEHOLDER,
  emptyChatGreeting,
  emptyChatPlaceholder,
  showSlidesEmptyCopy,
  SLIDES_COMPOSER_PLACEHOLDER,
} from './empty-chat-greeting';

const zen = {
  id: 'zen-1',
  name: 'Zen',
  class_name: 'zen.agents.ZenAgent/ZenAgent',
};
const abi = {
  id: 'abi-1',
  name: 'Abi',
  class_name: 'naas_abi.agents.AbiAgent/AbiAgent',
};
const slides = {
  id: 'slides-1',
  name: 'Slides',
  class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
};

describe('showSlidesEmptyCopy', () => {
  it('is true only for SlidesAgent, even when a deck is selected elsewhere', () => {
    expect(showSlidesEmptyCopy(slides)).toBe(true);
    expect(showSlidesEmptyCopy(zen)).toBe(false);
    expect(showSlidesEmptyCopy(abi)).toBe(false);
    expect(showSlidesEmptyCopy(null)).toBe(false);
    expect(showSlidesEmptyCopy(undefined)).toBe(false);
  });
});

describe('emptyChatGreeting', () => {
  it('keeps Zen and Abi on the generic greeting', () => {
    expect(emptyChatGreeting('Zen', 'Zen', zen)).toBe(
      'Hello, Zen. Zen here, how can I help?',
    );
    expect(emptyChatGreeting('Zen', 'Abi', abi)).toBe(
      'Hello, Zen. Abi here, how can I help?',
    );
  });

  it('uses the Minimal Light intro only for SlidesAgent', () => {
    expect(emptyChatGreeting('Zen', 'Slides', slides)).toBe(
      'Hello, Zen. This is a Minimal Light deck. Tell me the topic and I will write the slides.',
    );
  });

  it('falls back to Hello. when the user has no first name', () => {
    expect(emptyChatGreeting(undefined, 'Zen', zen)).toBe(
      'Hello. Zen here, how can I help?',
    );
  });
});

describe('emptyChatPlaceholder', () => {
  it('uses the deck prompt only for SlidesAgent', () => {
    expect(emptyChatPlaceholder(slides)).toBe(SLIDES_COMPOSER_PLACEHOLDER);
    expect(emptyChatPlaceholder(zen)).toBe(DEFAULT_COMPOSER_PLACEHOLDER);
    expect(emptyChatPlaceholder(abi)).toBe(DEFAULT_COMPOSER_PLACEHOLDER);
  });
});
