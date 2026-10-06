import { beforeEach, describe, expect, it } from 'vitest';

import type { Agent } from '@/stores/agents';
import { useAgentsStore } from '@/stores/agents';
import { useSheetsStore } from '@/stores/sheets';
import { useWorkspaceStore } from '@/stores/workspace';

import {
  pickSheetsOfficeAgent,
  pickWorkspaceDefaultAgent,
} from './pick-workspace-default-agent';
import {
  DEFAULT_SHEETS_TEMPLATE_ID,
  openSheetsAgentPane,
  parseFastApiDetail,
  sheetsApiErrorMessage,
  untitledSheetsSlug,
} from './create-sheets-project';

describe('untitledSheetsSlug', () => {
  it('is kebab-case and unique per timestamp', () => {
    const a = untitledSheetsSlug(1_700_000_000_000);
    const b = untitledSheetsSlug(1_700_000_000_001);
    expect(a).toMatch(/^untitled-[a-z0-9]+$/);
    expect(b).toMatch(/^untitled-[a-z0-9]+$/);
    expect(a).not.toBe(b);
  });
});

describe('DEFAULT_SHEETS_TEMPLATE_ID', () => {
  it('seeds Minimal Light', () => {
    expect(DEFAULT_SHEETS_TEMPLATE_ID).toBe('abi/grid-light-v1');
  });
});

/**
 * Opening the sheets pane used to write a model into the composer selection.
 * The server decides the sheets model and always has, so the pin was one side
 * of a negotiation the other side was never having: it picked gpt-4.1-mini,
 * the backend replaced it, and the two disagreed on every workbook.
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

describe('pickSheetsOfficeAgent', () => {
  it('prefers enabled Nexus Sheets over the workspace default', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const sheets = {
      id: 'sheets',
      enabled: true,
      isDefault: false,
      name: 'Sheets',
      class_name: 'naas_abi.agents.SheetsAgent/SheetsAgent',
    };
    expect(pickSheetsOfficeAgent([orchestrator, sheets])?.id).toBe('sheets');
  });

  it('falls back to the workspace default when Sheets is not on the roster', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const abi = { id: 'abi', enabled: true, isDefault: false, name: 'Abi' };
    expect(pickSheetsOfficeAgent([abi, orchestrator])?.id).toBe('default');
  });

  it('ignores an office agent that is not Nexus Sheets', () => {
    const orchestrator = { id: 'default', enabled: true, isDefault: true, name: 'Orchestrator' };
    const other = {
      id: 'sheet',
      enabled: true,
      isDefault: false,
      name: 'Office Sheets',
      class_name: 'acme.office.agents.SheetSheetsAgent/SheetSheetsAgent',
    };
    expect(pickSheetsOfficeAgent([orchestrator, other])?.id).toBe('default');
  });
});

describe('openSheetsAgentPane', () => {
  const ABI_ID = 'agent-abi';
  const DEFAULT_ID = 'agent-default';
  const SHEETS_ID = 'agent-sheets';
  const STALE_ID = 'agent-stale';

  const seedAgents = (withSheets = false): void => {
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
        ...(withSheets
          ? [
              {
                id: SHEETS_ID,
                name: 'Sheets',
                class_name: 'naas_abi.agents.SheetsAgent/SheetsAgent',
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
      sheetsPaneConversationByKey: {},
    });
    useSheetsStore.setState({ selectedSlug: null, selectedTitle: null });
  });

  it('leaves a selected model alone, including the free one the pin replaced', () => {
    useWorkspaceStore.setState({
      selectedChatModels: { [ABI_ID]: 'google/gemma-4-26b-a4b-it:free' },
    });

    openSheetsAgentPane();

    expect(useWorkspaceStore.getState().selectedChatModels[ABI_ID]).toBe(
      'google/gemma-4-26b-a4b-it:free',
    );
  });

  it('does not seed a selection where the user never made one', () => {
    openSheetsAgentPane();

    expect(useWorkspaceStore.getState().selectedChatModels[ABI_ID]).toBeUndefined();
  });

  it('pins the workspace default when Sheets is not on the roster', () => {
    openSheetsAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
  });

  it('pins Nexus Sheets when the workspace enabled it', () => {
    seedAgents(true);
    openSheetsAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(SHEETS_ID);
  });

  it('keeps an explicit picker choice when no workbook is open', () => {
    useWorkspaceStore.setState({
      paneAgent: ABI_ID,
      paneAgentExplicitlySelected: true,
    });

    openSheetsAgentPane();

    expect(useWorkspaceStore.getState().paneAgent).toBe(ABI_ID);
  });

  it('binds Sheets on an open workbook even if another agent was picked', () => {
    seedAgents(true);
    useWorkspaceStore.setState({
      paneAgent: ABI_ID,
      paneAgentExplicitlySelected: true,
    });

    openSheetsAgentPane({ slug: 'workbook-a' });

    expect(useWorkspaceStore.getState().paneAgent).toBe(SHEETS_ID);
  });

  it('resets a leftover picker choice when opening a new workbook', () => {
    useWorkspaceStore.setState({
      paneAgent: STALE_ID,
      paneAgentExplicitlySelected: true,
    });

    openSheetsAgentPane({ freshChat: true });

    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
    expect(useWorkspaceStore.getState().paneAgentExplicitlySelected).toBe(false);
    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
  });

  it('opens the thread bound to that workbook and does not keep the previous one', () => {
    const now = new Date();
    useWorkspaceStore.setState({
      paneConversationId: 'conv-a',
      sheetsPaneConversationByKey: { 'ws-1::workbook-b': 'conv-b' },
      conversations: [
        {
          id: 'conv-a',
          workspaceId: 'ws-1',
          title: 'Workbook A thread',
          messages: [],
          agent: SHEETS_ID,
          createdAt: now,
          updatedAt: now,
          sheetsSlug: 'workbook-a',
        },
        {
          id: 'conv-b',
          workspaceId: 'ws-1',
          title: 'Workbook B thread',
          messages: [],
          agent: SHEETS_ID,
          createdAt: now,
          updatedAt: now,
          sheetsSlug: 'workbook-b',
        },
      ],
    });

    openSheetsAgentPane({ slug: 'workbook-b', title: 'Workbook B' });

    expect(useWorkspaceStore.getState().paneConversationId).toBe('conv-b');
  });

  it('starts a fresh pane thread when the workbook has no conversation', () => {
    useWorkspaceStore.setState({
      paneConversationId: 'conv-a',
      conversations: [
        {
          id: 'conv-a',
          workspaceId: 'ws-1',
          title: 'Workbook A thread',
          messages: [],
          agent: SHEETS_ID,
          createdAt: new Date(),
          updatedAt: new Date(),
          sheetsSlug: 'workbook-a',
        },
      ],
    });

    openSheetsAgentPane({ slug: 'workbook-b', title: 'Workbook B' });

    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
  });
});

describe('parseFastApiDetail', () => {
  it('reads a string detail', () => {
    expect(parseFastApiDetail('Forgejo is not configured. Sheets needs git storage.')).toBe(
      'Forgejo is not configured. Sheets needs git storage.',
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

describe('sheetsApiErrorMessage', () => {
  it('rewrites a raw repo id into a human cause', () => {
    expect(sheetsApiErrorMessage('abi/monorepo', 'Failed (502)')).toBe(
      "Git repo 'abi/monorepo' is missing. Forgejo is not configured, or coding-init did not seed it.",
    );
  });

  it('keeps a real 503 message', () => {
    expect(
      sheetsApiErrorMessage('Forgejo is not configured. Sheets needs git storage.', 'Failed'),
    ).toBe('Forgejo is not configured. Sheets needs git storage.');
  });
});
