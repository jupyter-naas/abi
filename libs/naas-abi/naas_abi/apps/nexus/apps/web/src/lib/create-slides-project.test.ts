import { beforeEach, describe, expect, it } from 'vitest';

import type { Agent } from '@/stores/agents';
import { useAgentsStore } from '@/stores/agents';
import { useWorkspaceStore } from '@/stores/workspace';

import {
  DEFAULT_SLIDES_TEMPLATE_ID,
  openSlidesAgentPane,
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
    expect(DEFAULT_SLIDES_TEMPLATE_ID).toBe('abi/minimal-light-v1');
  });
});

/**
 * Opening the slides pane used to write a model into the composer selection.
 * The server decides the slides model and always has, so the pin was one side
 * of a negotiation the other side was never having: it picked gpt-4.1-mini,
 * the backend replaced it, and the two disagreed on every deck.
 *
 * These assert the call site stopped writing, not that a constant is gone.
 * Checking the export would only prove a declaration was deleted, which says
 * nothing about whether anything still reaches into the store.
 */
describe('openSlidesAgentPane', () => {
  const ABI_ID = 'agent-abi';

  const seedAgent = (): void => {
    useAgentsStore.setState({
      agents: [
        {
          id: ABI_ID,
          name: 'Abi',
          class_name: 'naas_abi.agents/AbiAgent',
          enabled: true,
          isDefault: true,
          modelIds: ['gpt-4.1-mini', 'anthropic/claude-sonnet-5'],
        } as Agent,
      ],
    });
  };

  beforeEach(() => {
    seedAgent();
    useWorkspaceStore.setState({ selectedChatModels: {}, paneAgentExplicitlySelected: false });
  });

  it('leaves a selected model alone, including the free one the pin replaced', () => {
    useWorkspaceStore.setState({
      selectedChatModels: { [ABI_ID]: 'google/gemma-4-26b-a4b-it:free' },
    });

    openSlidesAgentPane();

    expect(useWorkspaceStore.getState().selectedChatModels[ABI_ID]).toBe(
      'google/gemma-4-26b-a4b-it:free',
    );
  });

  it('does not seed a selection where the user never made one', () => {
    openSlidesAgentPane();

    expect(useWorkspaceStore.getState().selectedChatModels[ABI_ID]).toBeUndefined();
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
