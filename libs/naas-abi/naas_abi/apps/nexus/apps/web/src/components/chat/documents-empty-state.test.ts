import { describe, expect, it } from 'vitest';
import { sectionsEmptyStateCopy } from './documents-empty-state';

describe('sectionsEmptyStateCopy', () => {
  it('names the pane agent and omits an unknown template', () => {
    expect(sectionsEmptyStateCopy({ firstName: 'Admin', agentName: 'Abi' })).toBe(
      'Hello, Admin. I am Abi. Tell me the topic and I will write the documents.',
    );
  });

  it('adds a catalog template name when one is known', () => {
    expect(
      sectionsEmptyStateCopy({
        firstName: 'Admin',
        agentName: 'Abi',
        templateName: 'Consulting',
      }),
    ).toBe(
      'Hello, Admin. I am Abi. This is a Consulting document. Tell me the topic and I will write the documents.',
    );
  });

  it('names Documents when that agent is bound', () => {
    expect(sectionsEmptyStateCopy({ firstName: 'Admin', agentName: 'Documents' })).toBe(
      'Hello, Admin. I am Documents. Tell me the topic and I will write the documents.',
    );
  });

  it('skips I am when the pane has no agent name', () => {
    expect(sectionsEmptyStateCopy({ firstName: 'Admin' })).toBe(
      'Hello, Admin. Tell me the topic and I will write the documents.',
    );
  });
});
