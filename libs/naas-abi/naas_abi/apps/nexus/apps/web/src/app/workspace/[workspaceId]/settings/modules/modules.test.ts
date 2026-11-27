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
const wholeSwitch = (m: Mounted, key: string) =>
  m.host.querySelector(`tr[data-module="${key}"] [role="switch"]`) as HTMLButtonElement | null;

describe('Settings › Access › Modules', () => {
  it('lists each module and kind as Users does, whole or not, with a count and a filter', async () => {
    const parts = setup();
    const m = await render(parts);
    expect(parts.api.publishers).toHaveBeenCalledWith(WS);
    expect(rowKeys(m)).toEqual(['agents|acme.people', 'workflows|acme.sales']);
    expect(wholeSwitch(m, 'agents|acme.people')?.getAttribute('aria-checked')).toBe('true');
    expect(wholeSwitch(m, 'workflows|acme.sales')?.getAttribute('aria-checked')).toBe('false');
    expect(m.host.textContent).toContain('2 modules');

    await pickColumnFilter(m, 'offer', 'Not offered');
    expect(rowKeys(m)).toEqual(['workflows|acme.sales']);
  });

  it('offers a module whole, or unfolds it to offer item by item, each saved at once', async () => {
    const after = {
      ...OFFER,
      offered: { ...OFFER.offered, workflows: [{ module: 'acme.sales', name: 'Sync' }] },
    } as OfferState;
    const parts = setup(after);
    const m = await render(parts);

    await m.click(m.host.querySelector('tr[data-module="workflows|acme.sales"] [data-action="items"]'));
    await m.flush();
    expect(parts.api.resources).toHaveBeenCalledWith({
      scope: WS,
      service: 'module',
      type: 'workflow',
      module: 'acme.sales',
      limit: 200,
    });
    await m.click(m.host.querySelector('[data-offer-item="acme.sales/Sync"] [role="switch"]'));
    await m.flush();
    expect(parts.offerApi.save).toHaveBeenCalledWith(
      'ws-1',
      [{ kind: 'workflows', module: 'acme.sales', name: 'Sync', offered: true }],
      null,
    );
    expect(m.host.querySelector('[data-modules-notice]')?.textContent).toBe('Sync added to the offer.');
    expect(m.host.querySelector('tr[data-module="workflows|acme.sales"] [data-field="offer"]')?.textContent).toContain(
      '1 item: Sync',
    );

    await m.click(wholeSwitch(m, 'agents|acme.people'));
    await m.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith(
      'ws-1',
      [{ kind: 'agents', module: 'acme.people', name: '*', offered: false }],
      null,
    );
  });

  it('is read-only when IAM does not let the caller change "<W> access"', async () => {
    const parts = setup();
    parts.offerApi.read.mockResolvedValue({ ...OFFER, editable: false });
    const m = await render(parts);
    expect(wholeSwitch(m, 'agents|acme.people')?.disabled).toBe(true);
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

    await mounted.click(wholeSwitch(mounted, 'agents|acme.people'));
    await mounted.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith(
      'ws-1',
      [{ kind: 'agents', module: 'acme.people', name: '*', offered: true }],
      'pol_grants',
    );
    expect(mounted.host.querySelector('[data-modules-notice]')?.textContent).toBe(
      'Every agent of acme.people added to Analysts grants.',
    );
  });
});
