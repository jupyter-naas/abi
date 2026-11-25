// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const AGENTS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      id: `agent-${n}`,
      name: `Agent ${n}`,
      description: i === 36 ? 'Watches the zebra herd' : `The agent number ${n}`,
      icon: 'bot',
      logoUrl: null,
      provider: null,
      providerId: null,
      // The first four have no model: the "Model assigned" filter keeps 41.
      modelId: i < 4 ? null : 'gpt-test',
    };
  }),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/workspace/ws-1/settings/agents',
}));
vi.mock('@/stores/integrations', () => ({ useIntegrationsStore: () => ({ providers: [] }) }));
vi.mock('@/stores/models', () => ({
  useModelsStore: () => ({ models: [], fetchModels: () => undefined }),
  modelDisplayName: () => null,
}));
vi.mock('@/stores/agents', () => ({
  SETTINGS_RECONCILE_MS: 0,
  ensureAgentsSynced: async () => undefined,
  useAgentsStore: () => ({
    agents: AGENTS,
    addAgent: async () => undefined,
    deleteAgent: () => undefined,
    fetchAgents: async () => undefined,
  }),
}));

import AgentsPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Agents', () => {
  it('shows 20 agents a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(AgentsPage, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-agent',
      total: 45,
      search: 'input[placeholder="Search agents..."]',
      far: { id: 'agent-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Model"]', value: 'assigned' },
    });
  });
});
