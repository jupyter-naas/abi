// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

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
      // The first four have no model: the Models column filtered on gpt-test keeps 41.
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
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Agents', () => {
  it('shows 20 agents a page, searches all of them, a column filter goes back to the first page', async () => {
    mounted = await mount(AgentsPage, {});
    await mounted.flush();
    const m = mounted;
    const q = (selector: string) => m.host.querySelector(selector);
    const rows = () => [...m.host.querySelectorAll('[data-agent]')].map((r) => r.getAttribute('data-agent'));
    const shown = () => q('[data-field="rows-shown"]')?.textContent ?? null;

    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    expect(rows()).not.toContain('agent-37');
    await m.select(q('[data-field="page-size"]'), '50');
    expect(rows()).toHaveLength(45);
    await m.select(q('[data-field="page-size"]'), '20');
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toBe('Rows 21–40 of 45');

    // The search reaches every agent, not only the page shown.
    await m.type(q('input[placeholder="Search agents..."]'), 'zebra');
    expect(rows()).toEqual(['agent-37']);
    expect(m.host.textContent).toContain('1 of 45 agents');

    // The Models column filters on the model, and goes back to the first page.
    await m.type(q('input[placeholder="Search agents..."]'), '');
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await filterColumn(m, 'models', 'gpt-test');
    expect(shown()).toBe('Rows 1–20 of 41');
    expect(m.host.textContent).toContain('41 of 45 agents');
    expect(rows()).not.toContain('agent-01');

    await m.click(q('[data-action="clear-filters"]'));
    expect(shown()).toBe('Rows 1–20 of 45');
    // 45 agents drawn several times over: more than the default 5 s while the whole suite runs.
  }, 15_000);

  it('lists an agent without a model as Not assigned, a value of the Models filter', async () => {
    mounted = await mount(AgentsPage, {});
    await mounted.flush();
    await filterColumn(mounted, 'models', 'Not assigned');
    expect([...mounted.host.querySelectorAll('[data-agent]')].map((r) => r.getAttribute('data-agent'))).toEqual([
      'agent-01',
      'agent-02',
      'agent-03',
      'agent-04',
    ]);
    expect(mounted.host.querySelector('[data-agent="agent-01"] [data-field="models"]')?.textContent).toBe(
      'Not assigned',
    );
    expect(mounted.host.querySelector('[data-action="export"]')).not.toBeNull();
  });
});
