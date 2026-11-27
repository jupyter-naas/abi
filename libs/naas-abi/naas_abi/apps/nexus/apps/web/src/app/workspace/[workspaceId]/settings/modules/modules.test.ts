// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { OfferApi, OfferState } from '@/lib/access-model/workspace-offer';
import type { ResourceQuery } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { pickColumnFilter } from '@/lib/testing/column-filter';
import { WS, fakeApi, publishedType, resourcePage } from '@/components/access/access-fixtures';
import { WorkspaceModules } from './modules';

vi.mock('@/hooks/use-workspace-resources', () => ({ reloadWorkspaceResources: vi.fn() }));

const OFFER = {
  workspace_id: 'ws-1',
  scope: WS,
  access_policy: { id: 'pol_w', name: 'Sales access', owner_scope: WS },
  editable: true,
  whole_module: '*',
  offered: { agents: [{ module: 'acme.people', name: '*' }], apps: [], workflows: [], pipelines: [] },
} as OfferState;

const PUBLISHERS = {
  scope: WS,
  publishers: [
    {
      id: 'acme.people',
      kind: 'module' as const,
      types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/*']]], { module: 'acme.people' })],
    },
    {
      id: 'acme.sales',
      kind: 'module' as const,
      types: [publishedType('module', 'workflow', [['module:RunWorkflow', ['${scope}/module:workflow/acme.sales/*']]], { module: 'acme.sales' })],
    },
  ],
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

function setup(after: OfferState = OFFER) {
  const offerApi = { read: vi.fn().mockResolvedValue(OFFER), save: vi.fn().mockResolvedValue(after) };
  const api = fakeApi({
    publishers: vi.fn().mockResolvedValue(PUBLISHERS),
    resources: vi.fn((query: ResourceQuery) =>
      Promise.resolve(resourcePage('module', query.type, [['acme.sales/Sync', 'Sync'], ['acme.sales/Report', 'Report']])),
    ),
  });
  return { offerApi, api };
}

async function render(parts: ReturnType<typeof setup>) {
  mounted = await mount(WorkspaceModules, {
    workspaceId: 'ws-1',
    api: parts.api,
    offerApi: parts.offerApi as unknown as OfferApi,
  });
  await mounted.flush();
  return mounted;
}

const rowKeys = (m: Mounted) => [...m.host.querySelectorAll('tr[data-module]')].map((r) => r.getAttribute('data-module'));
const moduleSwitch = (m: Mounted, module: string) =>
  m.host.querySelector(`tr[data-module="${module}"] input[data-offer-switch]`) as HTMLInputElement | null;
const kindSwitch = (m: Mounted, key: string) =>
  m.host.querySelector(`tr[data-module-kind="${key}"] input[data-offer-switch]`) as HTMLInputElement | null;

describe('Settings › Access › Modules', () => {
  it('lists one row per module, offered whole, in part or not, with a count and a filter', async () => {
    const parts = setup();
    const m = await render(parts);
    expect(parts.api.publishers).toHaveBeenCalledWith(WS);
    expect(rowKeys(m)).toEqual(['acme.people', 'acme.sales']);
    expect(moduleSwitch(m, 'acme.people')?.checked).toBe(true);
    expect(moduleSwitch(m, 'acme.sales')?.checked).toBe(false);
    expect(m.host.querySelector('tr[data-module="acme.people"]')?.textContent).toContain('Agents');
    // Its contents are folded until asked.
    expect(m.host.querySelector('tr[data-module-kind]')).toBeNull();
    expect(m.host.textContent).toContain('2 modules');

    await pickColumnFilter(m, 'offer', 'Not offered');
    expect(rowKeys(m)).toEqual(['acme.sales']);
  });

  it('unfolds a module by its contents, then a kind item by item, each level switched at once', async () => {
    const after = {
      ...OFFER,
      offered: { ...OFFER.offered, workflows: [{ module: 'acme.sales', name: 'Sync' }] },
    } as OfferState;
    const parts = setup(after);
    const m = await render(parts);

    await m.click(m.host.querySelector('tr[data-module="acme.sales"] [data-action="contents"]'));
    expect(kindSwitch(m, 'workflows|acme.sales')?.checked).toBe(false);
    // Its contents one step in, their items two.
    expect(m.host.querySelector('tr[data-module-kind="workflows|acme.sales"] td:nth-child(2)')?.classList).toContain('access-offer-indent-1');
    await m.click(m.host.querySelector('tr[data-module-kind="workflows|acme.sales"] [data-action="items"]'));
    await m.flush();
    // Each item a row: its name two steps in, its switch in the Offered column.
    const item = m.host.querySelector('tr[data-offer-item="acme.sales/Sync"]')!;
    expect(item.querySelector('td:nth-child(2)')?.classList).toContain('access-offer-indent-2');
    expect(item.querySelector('td[data-field="offer"] input[data-offer-switch]')).not.toBeNull();
    expect(parts.api.resources).toHaveBeenCalledWith({
      scope: WS,
      service: 'module',
      type: 'workflow',
      module: 'acme.sales',
      limit: 200,
    });
    await m.click(m.host.querySelector('[data-offer-item="acme.sales/Sync"] input[data-offer-switch]'));
    await m.flush();
    expect(parts.offerApi.save).toHaveBeenCalledWith(
      'ws-1',
      [{ kind: 'workflows', module: 'acme.sales', name: 'Sync', offered: true }],
      null,
    );
    expect(m.host.querySelector('[data-modules-notice]')?.textContent).toBe('Sync added to the offer.');
    expect(m.host.querySelector('tr[data-module-kind="workflows|acme.sales"] [data-field="offer"]')?.textContent).toContain(
      '1 item: Sync',
    );
    // The module, offered in part now: its row says which part.
    expect(m.host.querySelector('tr[data-module="acme.sales"] [data-field="offer"]')?.textContent).toContain(
      'Workflows: 1 item',
    );
  });

  it('offers or takes back a whole module at once, every kind of it', async () => {
    const parts = setup();
    const m = await render(parts);
    await m.click(moduleSwitch(m, 'acme.people'));
    await m.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith(
      'ws-1',
      [{ kind: 'agents', module: 'acme.people', name: '*', offered: false }],
      null,
    );
    await m.click(moduleSwitch(m, 'acme.sales'));
    await m.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith(
      'ws-1',
      [{ kind: 'workflows', module: 'acme.sales', name: '*', offered: true }],
      null,
    );
    expect(m.host.querySelector('[data-modules-notice]')?.textContent).toBe('acme.sales added to the offer.');
  });

  it('offers or takes back the modules selected in one write, the filtered ones with select all', async () => {
    const parts = setup();
    const m = await render(parts);
    // The Offered filter keeps acme.sales (not offered): select all takes it alone.
    await pickColumnFilter(m, 'offer', 'Not offered');
    await m.click(m.host.querySelector('thead input[data-action="select-all"]'));
    expect(m.host.querySelector('[data-bulk-bar]')?.textContent).toContain('1 module selected');
    await m.click(m.host.querySelector('[data-bulk-bar] [data-bulk-action="offer"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Offer 1 module whole?');
    const confirm = [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find(
      (b) => b.textContent === 'Offer',
    )!;
    await m.click(confirm);
    await m.flush();
    expect(parts.offerApi.save).toHaveBeenCalledWith(
      'ws-1',
      [{ kind: 'workflows', module: 'acme.sales', name: '*', offered: true }],
      null,
    );
  });

  it("opens on a module's row when another page links to it (`?module=`)", async () => {
    const parts = setup();
    mounted = await mount(WorkspaceModules, {
      workspaceId: 'ws-1',
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      initialSearch: 'acme.sales',
    });
    await mounted.flush();
    expect(rowKeys(mounted)).toEqual(['acme.sales']);
    expect((mounted.host.querySelector('input[type="text"]') as HTMLInputElement).value).toBe('acme.sales');
  });

  it("in a workspace's Settings, edits the policy picked in the column, with no dropdown of its own", async () => {
    const parts = setup();
    mounted = await mount(WorkspaceModules, {
      workspaceId: 'ws-1',
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      initialPolicy: 'pol_grants',
      policyPicker: false,
    });
    await mounted.flush();
    expect(parts.offerApi.read).toHaveBeenCalledWith('ws-1', 'pol_grants');
    expect(mounted.host.querySelector('[data-policy-picker]')).toBeNull();
    expect(mounted.host.querySelector('select[data-field="policy"]')).toBeNull();
  });

  it('is read-only when IAM does not let the caller change "<W> access"', async () => {
    const parts = setup();
    parts.offerApi.read.mockResolvedValue({ ...OFFER, editable: false });
    const m = await render(parts);
    expect(moduleSwitch(m, 'acme.people')?.disabled).toBe(true);
    expect(m.host.textContent).toContain('Read-only: IAM does not let you change Sales access.');
  });

  it('edits another policy of the workspace, picked in the header', async () => {
    const GRANTS = { id: 'pol_grants', name: 'Analysts grants', owner_scope: WS };
    const ACCESS = OFFER.access_policy!;
    const onOffer = { ...OFFER, policy: ACCESS, policies: [ACCESS, GRANTS] } as OfferState;
    const onGrants = {
      ...onOffer,
      policy: GRANTS,
      offered: { agents: [], apps: [], workflows: [], pipelines: [] },
    } as OfferState;
    const parts = setup(onGrants);
    parts.offerApi.read.mockImplementation(async (_ws: string, policy?: string | null) =>
      policy === 'pol_grants' ? onGrants : onOffer,
    );
    const onPolicyChange = vi.fn();
    mounted = await mount(WorkspaceModules, {
      workspaceId: 'ws-1',
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      onPolicyChange,
    });
    await mounted.flush();
    await mounted.select(mounted.host.querySelector('select[data-field="policy"]'), 'pol_grants');
    await mounted.flush();
    expect(parts.offerApi.read).toHaveBeenLastCalledWith('ws-1', 'pol_grants');
    expect(onPolicyChange).toHaveBeenCalledWith('pol_grants');
    expect(mounted.host.textContent).toContain('2 modules');

    await mounted.click(moduleSwitch(mounted, 'acme.people'));
    await mounted.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith(
      'ws-1',
      [{ kind: 'agents', module: 'acme.people', name: '*', offered: true }],
      'pol_grants',
    );
    expect(mounted.host.querySelector('[data-modules-notice]')?.textContent).toBe('acme.people added to Analysts grants.');
  });
});
