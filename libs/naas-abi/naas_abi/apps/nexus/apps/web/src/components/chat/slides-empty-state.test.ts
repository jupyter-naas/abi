import { describe, expect, it } from 'vitest';
import { slidesEmptyStateCopy } from './slides-empty-state';

describe('slidesEmptyStateCopy', () => {
  it('names the pane agent and omits an unknown template', () => {
    expect(slidesEmptyStateCopy({ firstName: 'Admin', agentName: 'Abi' })).toBe(
      'Hello, Admin. I am Abi. Tell me the topic and I will write the slides.',
    );
  });

  it('adds a catalog template name when one is known', () => {
    expect(
      slidesEmptyStateCopy({
        firstName: 'Admin',
        agentName: 'Abi',
        templateName: 'Consulting',
      }),
    ).toBe(
      'Hello, Admin. I am Abi. This is a Consulting deck. Tell me the topic and I will write the slides.',
    );
  });

  it('names Slides when that agent is bound', () => {
    expect(slidesEmptyStateCopy({ firstName: 'Admin', agentName: 'Slides' })).toBe(
      'Hello, Admin. I am Slides. Tell me the topic and I will write the slides.',
    );
  });

  it('skips I am when the pane has no agent name', () => {
    expect(slidesEmptyStateCopy({ firstName: 'Admin' })).toBe(
      'Hello, Admin. Tell me the topic and I will write the slides.',
    );
  });
});
