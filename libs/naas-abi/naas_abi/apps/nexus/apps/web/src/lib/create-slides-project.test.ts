import { beforeEach, describe, expect, it } from 'vitest';

import type { Agent } from '@/stores/agents';
import { useAgentsStore } from '@/stores/agents';
import { useSlidesStore } from '@/stores/slides';
import { useWorkspaceStore } from '@/stores/workspace';

import {
  pickSlidesOfficeAgent,
  pickWorkspaceDefaultAgent,
} from './pick-workspace-default-agent';
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
describe('pickWorkspaceDefaultAgent', () => {
  it('prefers the workspace default over Abi', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true };
    const abi = { id: 'abi', enabled: true, isDefault: false };
    expect(pickWorkspaceDefaultAgent([abi, orchestrator])?.id).toBe('default');
  });

  it('still picks the workspace default when sync left it disabled', () => {
    const orchestrator = { id: 'default', enabled: false, isDefault: true };
    const abi = { id: 'abi', enabled: false, isDefault: false };
    expect(pickWorkspaceDefaultAgent([abi, orchestrator])?.id).toBe('default');
  });
});

describe('pickSlidesOfficeAgent', () => {
  it('prefers enabled Nexus Slides over the workspace default', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const slides = {
      id: 'slides',
      enabled: true,
      isDefault: false,
      name: 'Slides',
      class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
    };
    expect(pickSlidesOfficeAgent([orchestrator, slides])?.id).toBe('slides');
  });

  it('falls back to the workspace default when Slides is not on the roster', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const abi = { id: 'abi', enabled: true, isDefault: false, name: 'Abi' };
    expect(pickSlidesOfficeAgent([abi, orchestrator])?.id).toBe('default');
  });

  it('ignores an office agent that is not Nexus Slides', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const other = {
      id: 'sheet',
      enabled: true,
      isDefault: false,
      name: 'Office Slides',
      class_name: 'acme.office.agents.SheetSlidesAgent/SheetSlidesAgent',
    };
    expect(pickSlidesOfficeAgent([orchestrator, other])?.id).toBe('default');
  });
});

describe('openSlidesAgentPane', () => {
  const ABI_ID = 'agent-abi';
  const DEFAULT_ID = 'agent-default';
  const SLIDES_ID = 'agent-slides';
  const STALE_ID = 'agent-stale';

  const seedAgents = (withSlides = false): void => {
    useAgentsStore.setState({
      agents: [
        {
          id: ABI_ID,
          name: 'Abi',
          class_name: 'naas_abi.agents/AbiAgent',
          enabled: true,
          isDefault: false,
          modelIds: ['gpt-4.1-mini', 'anthropic/claude-sonnet-5'],
        } as Agent,
        {
          id: DEFAULT_ID,
          name: 'Orchestrator',
          class_name: 'demo.agents/OrchestratorAgent',
          enabled: true,
          isDefault: true,
          modelIds: ['gpt-4.1-mini'],
        } as Agent,
        ...(withSlides
          ? [
              {
                id: SLIDES_ID,
                name: 'Slides',
                class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
                enabled: true,
                isDefault: false,
                modelIds: ['qwen-3.8'],
              } as Agent,
            ]
          : []),
      ],
    });
  };

  beforeEach(() => {
    seedAgents();
    useWorkspaceStore.setState({
      selectedChatModels: {},
      paneAgent: '',
      paneAgentExplicitlySelected: false,
      currentWorkspaceId: 'ws-1',
      conversations: [],
      paneConversationId: null,
      slidesPaneConversationByKey: {},
    });
    useSlidesStore.setState({ selectedSlug: null, selectedTitle: null });
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

  it('pins the workspace default when Slides is not on the roster', () => {
    openSlidesAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
  });

  it('pins Nexus Slides when the workspace enabled it', () => {
    seedAgents(true);
    openSlidesAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(SLIDES_ID);
  });

  it('keeps an explicit picker choice when no deck is open', () => {
    useWorkspaceStore.setState({
      paneAgent: ABI_ID,
      paneAgentExplicitlySelected: true,
    });

    openSlidesAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(ABI_ID);
  });

  it('binds Slides on an open deck even if another agent was picked', () => {
    seedAgents(true);
    useWorkspaceStore.setState({
      paneAgent: ABI_ID,
      paneAgentExplicitlySelected: true,
    });

    openSlidesAgentPane({ slug: 'deck-a' });

    expect(useWorkspaceStore.getState().paneAgent).toBe(SLIDES_ID);
  });

  it('resets a leftover picker choice when opening a new deck', () => {
    useWorkspaceStore.setState({
      paneAgent: STALE_ID,
      paneAgentExplicitlySelected: true,
    });

    openSlidesAgentPane({ freshChat: true });

    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
    expect(useWorkspaceStore.getState().paneAgentExplicitlySelected).toBe(false);
    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
  });

  it('opens the thread bound to that deck and does not keep the previous one', () => {
    const now = new Date();
    useWorkspaceStore.setState({
      paneConversationId: 'conv-a',
      slidesPaneConversationByKey: { 'ws-1::deck-b': 'conv-b' },
      conversations: [
        {
          id: 'conv-a',
          workspaceId: 'ws-1',
          title: 'Deck A thread',
          messages: [],
          agent: SLIDES_ID,
          createdAt: now,
          updatedAt: now,
          slidesSlug: 'deck-a',
        },
        {
          id: 'conv-b',
          workspaceId: 'ws-1',
          title: 'Deck B thread',
          messages: [],
          agent: SLIDES_ID,
          createdAt: now,
          updatedAt: now,
          slidesSlug: 'deck-b',
        },
      ],
    });

    openSlidesAgentPane({ slug: 'deck-b', title: 'Deck B' });

    expect(useWorkspaceStore.getState().paneConversationId).toBe('conv-b');
  });

  it('starts a fresh pane thread when the deck has no conversation', () => {
    useWorkspaceStore.setState({
      paneConversationId: 'conv-a',
      conversations: [
        {
          id: 'conv-a',
          workspaceId: 'ws-1',
          title: 'Deck A thread',
          messages: [],
          agent: SLIDES_ID,
          createdAt: new Date(),
          updatedAt: new Date(),
          slidesSlug: 'deck-a',
        },
      ],
    });

    openSlidesAgentPane({ slug: 'deck-b', title: 'Deck B' });

    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
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
