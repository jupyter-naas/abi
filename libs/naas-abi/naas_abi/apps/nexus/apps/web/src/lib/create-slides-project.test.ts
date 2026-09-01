import { describe, expect, it } from 'vitest';

import {
  DEFAULT_SLIDES_TEMPLATE_ID,
  PREFERRED_SLIDES_CHAT_MODEL,
  parseFastApiDetail,
  slidesApiErrorMessage,
  untitledSlidesSlug,
} from './create-slides-project';

describe('untitledSlidesSlug', () => {
  it('is kebab-case and unique per timestamp', () => {
    const a = untitledSlidesSlug(1_700_000_000_000);
    const b = untitledSlidesSlug(1_700_000_000_001);
    expect(a).toMatch(/^untitled-[a-z0-9]+$/);
    expect(b).toMatch(/^untitled-[a-z0-9]+$/);
    expect(a).not.toBe(b);
  });
});

describe('DEFAULT_SLIDES_TEMPLATE_ID', () => {
  it('seeds Minimal Light', () => {
    expect(DEFAULT_SLIDES_TEMPLATE_ID).toBe('minimal-light-v1');
  });
});

describe('PREFERRED_SLIDES_CHAT_MODEL', () => {
  it('uses the paid OpenRouter model from config', () => {
    expect(PREFERRED_SLIDES_CHAT_MODEL).toBe('gpt-4.1-mini');
  });
});

describe('parseFastApiDetail', () => {
  it('reads a string detail', () => {
    expect(parseFastApiDetail('Forgejo is not configured. Slides needs git storage.')).toBe(
      'Forgejo is not configured. Slides needs git storage.',
    );
  });

  it('reads object and validation-list details', () => {
    expect(parseFastApiDetail({ msg: 'Git setup temporarily unavailable' })).toBe(
      'Git setup temporarily unavailable',
    );
    expect(parseFastApiDetail([{ loc: ['body', 'title'], msg: 'Field required', type: 'missing' }])).toBe(
      'Field required',
    );
  });
});

describe('slidesApiErrorMessage', () => {
  it('rewrites a raw repo id into a human cause', () => {
    expect(slidesApiErrorMessage('abi/monorepo', 'Failed (502)')).toBe(
      "Git repo 'abi/monorepo' is missing. Forgejo is not configured, or coding-init did not seed it.",
    );
  });

  it('keeps a real 503 message', () => {
    expect(
      slidesApiErrorMessage('Forgejo is not configured. Slides needs git storage.', 'Failed'),
    ).toBe('Forgejo is not configured. Slides needs git storage.');
  });
});
