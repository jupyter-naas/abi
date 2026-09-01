import { describe, expect, it } from 'vitest';

import {
  DEFAULT_SLIDES_TEMPLATE_ID,
  PREFERRED_SLIDES_CHAT_MODEL,
  isSlidesAgent,
  parseFastApiDetail,
  pickSlidesAgentId,
  sanitizeSlidesTitle,
  slidesApiErrorMessage,
  untitledSlidesSlug,
} from './create-slides-project';

describe('sanitizeSlidesTitle', () => {
  it('trims and caps the folder title', () => {
    expect(sanitizeSlidesTitle('  Hormuz brief  ')).toBe('Hormuz brief');
    expect(sanitizeSlidesTitle('   ')).toBe('');
    expect(sanitizeSlidesTitle('x'.repeat(200)).length).toBe(120);
  });
});

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
  it('uses Claude Sonnet 5 via OpenRouter', () => {
    expect(PREFERRED_SLIDES_CHAT_MODEL).toBe('anthropic/claude-sonnet-5');
  });
});

describe('pickSlidesAgentId', () => {
  it('prefers SlidesAgent over Abi', () => {
    const agents = [
      { id: 'abi-1', name: 'Abi', class_name: 'naas_abi.agents.AbiAgent/AbiAgent', enabled: true },
      {
        id: 'slides-1',
        name: 'Slides',
        class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
        enabled: true,
      },
    ];
    expect(isSlidesAgent(agents[1])).toBe(true);
    expect(pickSlidesAgentId(agents)).toBe('slides-1');
  });

  it('falls back to Abi when Slides is missing', () => {
    const agents = [
      { id: 'abi-1', name: 'Abi', class_name: 'naas_abi.agents.AbiAgent/AbiAgent', enabled: true },
      { id: 'zen-1', name: 'Zen', class_name: 'zen.agents.ZenAgent/ZenAgent', enabled: true },
    ];
    expect(pickSlidesAgentId(agents)).toBe('abi-1');
  });

  it('ignores disabled Slides rows', () => {
    const agents = [
      {
        id: 'slides-off',
        name: 'Slides',
        class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
        enabled: false,
      },
      { id: 'abi-1', name: 'Abi', class_name: 'naas_abi.agents.AbiAgent/AbiAgent', enabled: true },
    ];
    expect(pickSlidesAgentId(agents)).toBe('abi-1');
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
