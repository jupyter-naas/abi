import { beforeEach, describe, expect, it } from 'vitest';

import type { Agent } from '@/stores/agents';
import { useAgentsStore } from '@/stores/agents';
import { useDocumentsStore } from '@/stores/documents';
import { useWorkspaceStore } from '@/stores/workspace';

import {
  pickDocumentsOfficeAgent,
  pickWorkspaceDefaultAgent,
} from './pick-workspace-default-agent';
import {
  DEFAULT_DOCUMENTS_TEMPLATE_ID,
  openDocumentsAgentPane,
  parseFastApiDetail,
  documentsApiErrorMessage,
  untitledDocumentSlug,
} from './create-documents-project';

describe('untitledDocumentSlug', () => {
  it('is kebab-case and unique per timestamp', () => {
    const a = untitledDocumentSlug(1_700_000_000_000);
    const b = untitledDocumentSlug(1_700_000_000_001);
    expect(a).toMatch(/^untitled-[a-z0-9]+$/);
    expect(b).toMatch(/^untitled-[a-z0-9]+$/);
    expect(a).not.toBe(b);
  });
});

describe('DEFAULT_DOCUMENTS_TEMPLATE_ID', () => {
  it('seeds Minimal Light', () => {
    expect(DEFAULT_DOCUMENTS_TEMPLATE_ID).toBe('abi/minimal-light-v1');
  });
});

/**
 * Opening the sections pane used to write a model into the composer selection.
 * The server decides the sections model and always has, so the pin was one side
 * of a negotiation the other side was never having: it picked gpt-4.1-mini,
 * the backend replaced it, and the two disagreed on every document.
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

describe('pickDocumentsOfficeAgent', () => {
  it('prefers enabled Nexus Documents over the workspace default', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const sections = {
      id: 'documents',
      enabled: true,
      isDefault: false,
      name: 'Documents',
      class_name: 'naas_abi.agents.DocumentsAgent/DocumentsAgent',
    };
    expect(pickDocumentsOfficeAgent([orchestrator, sections])?.id).toBe('documents');
  });

  it('falls back to the workspace default when Documents is not on the roster', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const abi = { id: 'abi', enabled: true, isDefault: false, name: 'Abi' };
    expect(pickDocumentsOfficeAgent([abi, orchestrator])?.id).toBe('default');
  });

  it('ignores an office agent that is not Nexus Documents', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const other = {
      id: 'sheet',
      enabled: true,
      isDefault: false,
      name: 'Office Documents',
      class_name: 'acme.office.agents.SheetDocumentsAgent/SheetDocumentsAgent',
    };
    expect(pickDocumentsOfficeAgent([orchestrator, other])?.id).toBe('default');
  });
});

describe('openDocumentsAgentPane', () => {
  const ABI_ID = 'agent-abi';
  const DEFAULT_ID = 'agent-default';
  const SLIDES_ID = 'agent-sections';
  const STALE_ID = 'agent-stale';

  const seedAgents = (withDocuments = false): void => {
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
        ...(withDocuments
          ? [
              {
                id: SLIDES_ID,
                name: 'Documents',
                class_name: 'naas_abi.agents.DocumentsAgent/DocumentsAgent',
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
      documentsPaneConversationByKey: {},
    });
    useDocumentsStore.setState({ selectedSlug: null, selectedTitle: null });
  });

  it('leaves a selected model alone, including the free one the pin replaced', () => {
    useWorkspaceStore.setState({
      selectedChatModels: { [ABI_ID]: 'google/gemma-4-26b-a4b-it:free' },
    });

    openDocumentsAgentPane();

    expect(useWorkspaceStore.getState().selectedChatModels[ABI_ID]).toBe(
      'google/gemma-4-26b-a4b-it:free',
    );
  });

  it('does not seed a selection where the user never made one', () => {
    openDocumentsAgentPane();

    expect(useWorkspaceStore.getState().selectedChatModels[ABI_ID]).toBeUndefined();
  });

  it('pins the workspace default when Documents is not on the roster', () => {
    openDocumentsAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
  });

  it('pins Nexus Documents when the workspace enabled it', () => {
    seedAgents(true);
    openDocumentsAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(SLIDES_ID);
  });

  it('keeps an explicit picker choice when no document is open', () => {
    useWorkspaceStore.setState({
      paneAgent: ABI_ID,
      paneAgentExplicitlySelected: true,
    });

    openDocumentsAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(ABI_ID);
  });

  it('binds Documents on an open document even if another agent was picked', () => {
    seedAgents(true);
    useWorkspaceStore.setState({
      paneAgent: ABI_ID,
      paneAgentExplicitlySelected: true,
    });

    openDocumentsAgentPane({ slug: 'document-a' });

    expect(useWorkspaceStore.getState().paneAgent).toBe(SLIDES_ID);
  });

  it('resets a leftover picker choice when opening a new document', () => {
    useWorkspaceStore.setState({
      paneAgent: STALE_ID,
      paneAgentExplicitlySelected: true,
    });

    openDocumentsAgentPane({ freshChat: true });

    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
    expect(useWorkspaceStore.getState().paneAgentExplicitlySelected).toBe(false);
    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
  });

  it('opens the thread bound to that document and does not keep the previous one', () => {
    const now = new Date();
    useWorkspaceStore.setState({
      paneConversationId: 'conv-a',
      documentsPaneConversationByKey: { 'ws-1::document-b': 'conv-b' },
      conversations: [
        {
          id: 'conv-a',
          workspaceId: 'ws-1',
          title: 'Document A thread',
          messages: [],
          agent: SLIDES_ID,
          createdAt: now,
          updatedAt: now,
          sectionsSlug: 'document-a',
        },
        {
          id: 'conv-b',
          workspaceId: 'ws-1',
          title: 'Document B thread',
          messages: [],
          agent: SLIDES_ID,
          createdAt: now,
          updatedAt: now,
          sectionsSlug: 'document-b',
        },
      ],
    });

    openDocumentsAgentPane({ slug: 'document-b', title: 'Document B' });

    expect(useWorkspaceStore.getState().paneConversationId).toBe('conv-b');
  });

  it('starts a fresh pane thread when the document has no conversation', () => {
    useWorkspaceStore.setState({
      paneConversationId: 'conv-a',
      conversations: [
        {
          id: 'conv-a',
          workspaceId: 'ws-1',
          title: 'Document A thread',
          messages: [],
          agent: SLIDES_ID,
          createdAt: new Date(),
          updatedAt: new Date(),
          sectionsSlug: 'document-a',
        },
      ],
    });

    openDocumentsAgentPane({ slug: 'document-b', title: 'Document B' });

    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
  });
});

describe('parseFastApiDetail', () => {
  it('reads a string detail', () => {
    expect(parseFastApiDetail('Forgejo is not configured. Documents needs git storage.')).toBe(
      'Forgejo is not configured. Documents needs git storage.',
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

describe('documentsApiErrorMessage', () => {
  it('rewrites a raw repo id into a human cause', () => {
    expect(documentsApiErrorMessage('abi/monorepo', 'Failed (502)')).toBe(
      "Git repo 'abi/monorepo' is missing. Forgejo is not configured, or coding-init did not seed it.",
    );
  });

  it('keeps a real 503 message', () => {
    expect(
      documentsApiErrorMessage('Forgejo is not configured. Documents needs git storage.', 'Failed'),
    ).toBe('Forgejo is not configured. Documents needs git storage.');
  });
});
