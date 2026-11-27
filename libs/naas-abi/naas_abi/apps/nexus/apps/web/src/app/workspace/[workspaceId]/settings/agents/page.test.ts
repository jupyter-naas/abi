// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
      // The first one comes from a module: its row links to the module in Access › Modules.
      class_name: i === 0 ? 'acme.people/Coach' : undefined,
    };
  }),
);

// The URL's search: no policy picked ("<W> access") unless a test sets `?policy=`.
const URL_SEARCH = vi.hoisted(() => ({ current: '' }));

vi.mock('next/navigation', () => ({
  // `usePolicyHref` and the Enabled column read the policy picked from the URL.
  useSearchParams: () => new URLSearchParams(URL_SEARCH.current),
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

// The module items: the offer and IAM's catalog, faked.
vi.mock('@/lib/access-model/workspace-offer', async (importOriginal) => {
  const { moduleItemsFake } = await import('@/lib/testing/module-items-fake');
  return { ...(await importOriginal<object>()), createOfferApi: () => moduleItemsFake.offer };
});
vi.mock('@/lib/iam-admin/api', async (importOriginal) => {
  const { moduleItemsFake } = await import('@/lib/testing/module-items-fake');
  return { ...(await importOriginal<object>()), createIamAdminApi: () => moduleItemsFake.iam };
});
vi.mock('@/hooks/use-workspace-resources', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  reloadWorkspaceResources: async () => undefined,
}));

import AgentsPage from './page';
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';
import { moduleItemsFake } from '@/lib/testing/module-items-fake';

let mounted: Mounted | null = null;
beforeEach(() => {
  URL_SEARCH.current = '';
  // acme.people brings Coach (agent-01), offered by name.
  moduleItemsFake.set({
    modules: { 'acme.people': { agent: [{ name: 'Coach' }] } },
    offered: { agents: [{ module: 'acme.people', name: 'Coach' }] },
  });
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const enabledBox = (m: Mounted, key: string) =>
  m.host.querySelector(`input[data-enabled="${key}"]`) as HTMLInputElement | null;
const notice = (m: Mounted) => m.host.querySelector('[data-module-items-notice]')?.textContent ?? null;
const confirmButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find((b) => b.textContent === label)!;

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
    // No count above the search: the badge says how many agents, the pager how many are shown.
    expect(m.host.textContent).not.toContain('1 of 45 agents');

    // The Models column filters on the model, and goes back to the first page.
    await m.type(q('input[placeholder="Search agents..."]'), '');
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await filterColumn(m, 'models', 'gpt-test');
    expect(shown()).toBe('Rows 1–20 of 41');
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

  it('says one total, creates with Create agent, and links a module agent to its row in Access › Modules', async () => {
    mounted = await mount(AgentsPage, {});
    await mounted.flush();
    expect(mounted.host.textContent).toContain('45 agents');
    const buttons = [...mounted.host.querySelectorAll('button')].map((b) => b.textContent);
    expect(buttons).toContain('Create agent');
    expect(buttons).not.toContain('Add Agent');
    const link = mounted.host.querySelector('[data-agent="agent-01"] a[data-module-link]');
    expect(link?.getAttribute('href')).toBe('/workspace/ws-1/settings/modules?module=acme.people');
    expect(link?.textContent).toBe('acme.people');
  });

  it('lists every agent of the modules, enabled or not, and enables one at once in the policy picked', async () => {
    URL_SEARCH.current = 'policy=pol_team';
    moduleItemsFake.set({
      modules: { 'acme.people': { agent: [{ name: 'Coach' }, { name: 'Recruiter' }] } },
      offered: { agents: [{ module: 'acme.people', name: 'Coach' }] },
    });
    const m = (mounted = await mount(AgentsPage, {}));
    await m.flush();
    expect(moduleItemsFake.reads).toEqual(['pol_team']);
    // Recruiter is disabled: the roster does not hold it, its row says what the catalog does.
    expect(m.host.textContent).toContain('46 agents');
    expect([...m.host.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(
      expect.arrayContaining(['Agent', 'Models', 'Enabled']),
    );
    await m.type(m.host.querySelector('input[placeholder="Search agents..."]'), 'Recruiter');
    const row = m.host.querySelector('[data-agent="agents|acme.people|Recruiter"]');
    expect(row?.querySelector('a[data-module-link]')?.getAttribute('href')).toBe(
      '/workspace/ws-1/settings/modules?module=acme.people&policy=pol_team',
    );
    expect(enabledBox(m, 'agents|acme.people|Recruiter')?.checked).toBe(false);
    expect(enabledBox(m, 'agents|acme.people|Recruiter')?.disabled).toBe(false);

    // A table of switches: the change is saved at once, and said.
    await m.click(enabledBox(m, 'agents|acme.people|Recruiter'));
    await m.flush();
    expect(moduleItemsFake.saves).toEqual([
      { changes: [{ kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true }], policyId: 'pol_team' },
    ]);
    expect(enabledBox(m, 'agents|acme.people|Recruiter')?.checked).toBe(true);
    expect(notice(m)).toBe('Recruiter enabled.');
  });

  it('disabling an agent of a module enabled whole turns that module item by item', async () => {
    moduleItemsFake.set({
      modules: { 'acme.people': { agent: [{ name: 'Coach' }, { name: 'Recruiter' }, { name: 'Scout' }] } },
      offered: { agents: [{ module: 'acme.people', name: '*' }] },
    });
    const m = (mounted = await mount(AgentsPage, {}));
    await m.flush();
    // agent-01 is Coach: its row keeps its own cells, and gains the checkbox.
    const coach = enabledBox(m, 'agents|acme.people|Coach');
    expect(coach?.closest('[data-agent]')?.getAttribute('data-agent')).toBe('agent-01');
    expect(coach?.checked).toBe(true);
    await m.click(coach);
    await m.flush();
    expect(moduleItemsFake.saves[0]).toEqual({
      changes: [
        { kind: 'agents', module: 'acme.people', name: '*', offered: false },
        { kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true },
        { kind: 'agents', module: 'acme.people', name: 'Scout', offered: true },
      ],
      policyId: null,
    });
    expect(enabledBox(m, 'agents|acme.people|Coach')?.checked).toBe(false);
    expect(notice(m)).toBe('Agent 01 disabled.');
  });

  it('enables the agents shown, selected all, in one save asked first', async () => {
    moduleItemsFake.set({
      modules: {
        'acme.people': { agent: [{ name: 'Coach' }, { name: 'Recruiter' }, { name: 'Scout' }] },
        'acme.market': { agent: [{ name: 'Trader' }] },
      },
    });
    const m = (mounted = await mount(AgentsPage, {}));
    await m.flush();
    // The search keeps acme.people's agents: select all takes those shown, not Trader.
    await m.type(m.host.querySelector('input[placeholder="Search agents..."]'), 'acme.people');
    expect(m.host.querySelectorAll('[data-agent]')).toHaveLength(3);
    await m.click(m.host.querySelector('thead input[data-action="select-all"]'));
    expect(m.host.querySelector('[data-bulk-bar]')?.textContent).toContain('3 agents selected');
    await m.click(m.host.querySelector('[data-bulk-bar] [data-bulk-action="on"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Enable 3 agents?');
    await m.click(confirmButton('Enable'));
    await m.flush();
    expect(moduleItemsFake.saves).toHaveLength(1);
    expect(moduleItemsFake.saves[0].changes.map((c) => `${c.module}/${c.name}:${c.offered}`).sort()).toEqual([
      'acme.people/Coach:true',
      'acme.people/Recruiter:true',
      'acme.people/Scout:true',
    ]);
    expect(notice(m)).toBe('3 agents enabled.');
    expect(m.host.querySelector('[data-bulk-bar]')).toBeNull();
  });

  it('keeps an agent the workspace builds always enabled, without a checkbox', async () => {
    const m = (mounted = await mount(AgentsPage, {}));
    await m.flush();
    const built = m.host.querySelector('[data-agent="agent-02"]');
    expect(built?.querySelector('[data-field="enabled"]')?.textContent).toBe('Always enabled');
    expect(built?.querySelector('[data-field="enabled"] input')).toBeNull();
    expect((built?.querySelector('input[data-select-row]') as HTMLInputElement | null)?.disabled).toBe(true);
    // The module agent's row may be selected.
    const coach = m.host.querySelector('[data-agent="agent-01"] input[data-select-row]') as HTMLInputElement | null;
    expect(coach?.disabled).toBe(false);
  });
});
