// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessApi } from './feature-access-api';
import type { AccessLevel } from '@/lib/access-model/access-levels';
import type { FeatureAccessState, FeatureRow } from './feature-access-model';
import { FeatureAccess } from './feature-access';

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});

const SCOPE = 'abi:nexus:organization/acme/nexus:workspace/ws1';
const CHAT_FILES = { id: 'pol_cf', name: 'Chat + Files', owner_scope: SCOPE, effect: 'Allow' as const, attached: true };
const MARKETPLACE = { id: 'pol_mkt', name: 'Marketplace', owner_scope: SCOPE, effect: 'Allow' as const, attached: false };

function row(over: Partial<FeatureRow> & Pick<FeatureRow, 'key' | 'label'>): FeatureRow {
  return {
    choice: 'nobody',
    principals: [],
    policy: null,
    hand_edited: false,
    offered: true,
    held: true,
    editable: true,
    reason: null,
    also: [],
    ...over,
  };
}

function state(features: FeatureRow[], errors?: Record<string, string>): FeatureAccessState {
  return {
    workspace_id: 'ws1',
    scope: SCOPE,
    access_policy: { id: 'pol_access', name: 'Alpha access', owner_scope: SCOPE },
    members_group: { id: 'grp_members', kind: 'group', name: 'Alpha members' },
    can: { create: true, attach: true, detach: true, widen: true },
    features,
    ...(errors ? { errors } : {}),
  };
}

const BEFORE = state([
  row({ key: 'chat', label: 'Chat', choice: 'everyone', also: [CHAT_FILES] }),
  row({ key: 'files', label: 'Files', also: [CHAT_FILES] }),
  row({ key: 'maps', label: 'Maps', also: [CHAT_FILES] }),
  row({ key: 'marketplace', label: 'Marketplace', also: [MARKETPLACE] }),
  row({ key: 'graph', label: 'Graph', offered: false }),
  row({
    key: 'search',
    label: 'Search',
    choice: 'everyone',
    policy: { id: 'pol_search', name: 'Feature · Search', owner_scope: SCOPE },
    hand_edited: true,
    editable: false,
    reason: 'Feature · Search was changed on its policy page: change it there.',
  }),
]);

function fakeApi(after?: FeatureAccessState) {
  return {
    read: vi.fn().mockResolvedValue(BEFORE),
    save: vi.fn().mockResolvedValue(after ?? BEFORE),
  };
}

const LEVELS: Record<string, AccessLevel> = {
  chat: 'admin',
  files: 'admin',
  maps: 'write',
  marketplace: 'admin',
  graph: 'admin',
  search: 'admin',
};

function levelRowOf(name: string, level: AccessLevel) {
  return {
    key: `feature:${name}`,
    kind: 'feature' as const,
    name,
    label: name,
    level,
    choices: ['none', 'read', 'write', 'admin'] as AccessLevel[],
    actions: { read: ['nexus:UseFeature'], write: ['nexus:CreateView'], admin: ['nexus:ConfigureFeature'] },
  };
}

function fakeLevels(levels: Record<string, AccessLevel> = LEVELS, mode: 'cap' | 'grant' = 'cap') {
  const levelsState = {
    workspace_id: 'ws1',
    kind: 'feature' as const,
    mode,
    access_policy: null,
    policy: null,
    policies: [],
    editable: true,
    reason: null,
    rows: Object.entries(levels).map(([name, level]) => levelRowOf(name, level)),
  };
  return {
    read: vi.fn().mockResolvedValue(levelsState),
    save: vi.fn(async (_ws: string, _kind: string, wanted: Record<string, AccessLevel>) => ({
      ...levelsState,
      rows: levelsState.rows.map((r) => (wanted[r.key] ? { ...r, level: wanted[r.key] } : r)),
    })),
  };
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(api: ReturnType<typeof fakeApi>, levelsApi: unknown = fakeLevels(), workspaceId = 'ws1') {
  mounted = await mount(FeatureAccess, {
    workspaceId,
    api: api as unknown as FeatureAccessApi,
    levelsApi: levelsApi as never,
  });
  await mounted.flush();
  return mounted;
}

const at = (m: Mounted, feature: string, selector: string) =>
  m.host.querySelector(`tr[data-feature="${feature}"] ${selector}`) as HTMLButtonElement | null;
const level = (m: Mounted, feature: string, value: AccessLevel) =>
  at(m, feature, `[data-access-level] [data-level="${value}"]`);
const picked = (m: Mounted, feature: string) =>
  at(m, feature, '[data-access-level] [aria-checked="true"]')?.getAttribute('data-level') ?? null;
const saveButton = (m: Mounted) => m.host.querySelector('[data-action="save"]') as HTMLButtonElement;

describe('FeatureAccess', () => {
  it('shows each feature, the Nexus Files one included: its description, its access (no Enabled column), a link to its page', async () => {
    const m = await render(fakeApi());

    // Graph, which the organization does not offer, is not shown in the workspace.
    expect([...m.host.querySelectorAll('tr[data-feature]')].map((tr) => tr.getAttribute('data-feature'))).toEqual([
      'chat',
      'files',
      'maps',
      'marketplace',
      'search',
    ]);
    expect([...m.host.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual([
      'Feature',
      'Description',
      'Access',
      '',
    ]);
    expect(m.host.querySelector('input[data-enabled]')).toBeNull();
    expect(at(m, 'maps', '[data-field="description"]')?.textContent).toContain('feeds');
    expect(picked(m, 'chat')).toBe('admin');
    // Maps is taken out (Nobody): None, whatever level is stored.
    expect(picked(m, 'maps')).toBe('none');
    // Other policies are edited from the Policy dropdown: no column of them.
    expect(m.host.querySelector('[data-effect]')).toBeNull();
    expect(at(m, 'agents', 'a')).toBeNull();
    expect(at(m, 'files', '[data-action="configure"]')?.getAttribute('href')).toBe('/workspace/ws1/settings/files');
    expect(at(m, 'maps', '[data-action="configure"]')?.getAttribute('href')).toBe('/workspace/ws1/settings/maps');
    // What Access is used for, None included, said above the table.
    expect(m.host.querySelector('[data-access-legend]')?.textContent).toContain('how far people go');
    expect(m.host.querySelector('[data-access-legend]')?.textContent).toContain('None takes it out');
    expect(m.host.textContent).toContain('admins included');
    // Features are the workspace's offer: the description links to "<W> access".
    expect(m.host.querySelector('a[href*="pol_access"]')?.textContent).toBe('Alpha access');
    expect(saveButton(m).disabled).toBe(true);
  });

  it('makes a hand-edited row read-only with a link, and a feature still allowed but no longer offered above None-only', async () => {
    const api = fakeApi();
    api.read.mockResolvedValue(
      state([
        ...BEFORE.features.filter((r) => r.key !== 'graph'),
        row({ key: 'graph', label: 'Graph', choice: 'everyone', offered: false }),
      ]),
    );
    const m = await render(api);

    expect(level(m, 'search', 'none')?.disabled).toBe(true);
    expect(level(m, 'search', 'read')?.disabled).toBe(true);
    expect(at(m, 'search', 'p.workspace-features-note')?.textContent).toContain('read-only here');
    expect(at(m, 'search', 'p.workspace-features-note a')?.getAttribute('href')).toContain('pol_search');

    // Still allowed here, not offered above: shown, and it can only be taken out (None).
    expect(picked(m, 'graph')).toBe('admin');
    expect(level(m, 'graph', 'none')?.disabled).toBe(false);
    expect(level(m, 'graph', 'read')?.disabled).toBe(true);
    expect(at(m, 'graph', 'p.workspace-features-note')?.textContent).toContain('Not offered in this workspace');
    expect(at(m, 'graph', 'p.workspace-features-note a')?.textContent).toBe('Widen Alpha access');
  });

  it('puts features in at the level picked, in one save, and keeps the refused one as a draft', async () => {
    const after = state(
      [
        ...BEFORE.features.filter((r) => r.key !== 'maps'),
        row({ key: 'maps', label: 'Maps', choice: 'everyone', also: [CHAT_FILES] }),
      ],
      { marketplace: 'IAM refused the attachment.' },
    );
    const api = fakeApi(after);
    const levelsApi = fakeLevels();
    const m = await render(api, levelsApi);

    await m.click(level(m, 'maps', 'read'));
    await m.click(level(m, 'marketplace', 'write'));
    expect(m.host.textContent).toContain('2 unsaved changes');

    await m.click(saveButton(m));
    await m.flush();
    expect(api.save).toHaveBeenCalledTimes(1);
    expect(api.save).toHaveBeenCalledWith(
      'ws1',
      [
        { feature: 'maps', choice: 'everyone' },
        { feature: 'marketplace', choice: 'everyone' },
      ],
      null,
    );
    // The refused feature's level is not written.
    expect(levelsApi.save).toHaveBeenCalledWith('ws1', 'feature', { 'feature:maps': 'read' }, null);
    expect(picked(m, 'maps')).toBe('read');
    expect(at(m, 'marketplace', '[role="alert"]')?.textContent).toBe('IAM refused the attachment.');
    expect(picked(m, 'marketplace')).toBe('write');
    expect(m.host.textContent).toContain('1 unsaved change');
  });

  it('takes a feature out with None: Nobody, and capped at None', async () => {
    const api = fakeApi();
    const levelsApi = fakeLevels();
    const m = await render(api, levelsApi);

    await m.click(level(m, 'chat', 'none'));
    await m.click(saveButton(m));
    await m.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', [{ feature: 'chat', choice: 'nobody' }], null);
    expect(levelsApi.save).toHaveBeenCalledWith('ws1', 'feature', { 'feature:chat': 'none' }, null);
  });

  it('lays the features out as Users: a count, a search that narrows the table, columns that sort', async () => {
    const m = await render(fakeApi());
    const keys = () => [...m.host.querySelectorAll('tr[data-feature]')].map((tr) => tr.getAttribute('data-feature'));

    expect(m.host.textContent).toContain('2 offered · 3 not offered');
    expect(m.host.textContent).toContain('5 features');
    await m.click(m.host.querySelector('[data-sort="access"]'));
    expect(keys()).toEqual(['chat', 'search', 'files', 'maps', 'marketplace']);

    await m.type(m.host.querySelector('input[type="search"], input') as HTMLInputElement, 'feeds');
    expect(keys()).toEqual(['maps']);
    expect(m.host.textContent).toContain('1 of 5 features');
    await m.click(m.host.querySelector('[data-action="clear-filters"]'));
    expect(keys()).toHaveLength(5);
  });

  it('discards the drafts, and a pick back to what the row holds is no change', async () => {
    const api = fakeApi();
    const m = await render(api);

    await m.click(level(m, 'chat', 'none'));
    expect(m.host.textContent).toContain('1 unsaved change');
    await m.click(level(m, 'chat', 'admin'));
    expect(m.host.textContent).toContain('No unsaved change');

    await m.click(level(m, 'chat', 'read'));
    await m.click(m.host.querySelector('[data-action="discard"]'));
    expect(picked(m, 'chat')).toBe('admin');
    expect(m.host.textContent).toContain('No unsaved change');
    expect(api.save).not.toHaveBeenCalled();
  });

  it('edits another policy of the workspace, picked in the header: what it grants, saved into it', async () => {
    const GRANTS = { id: 'pol_grants', name: 'Analysts grants', owner_scope: SCOPE };
    const ACCESS = { id: 'pol_access', name: 'Alpha access', owner_scope: SCOPE };
    const onOffer = { ...BEFORE, policy: ACCESS, policies: [ACCESS, GRANTS] };
    const onGrants = { ...onOffer, policy: GRANTS };
    const api = {
      read: vi.fn(async (_ws: string, policy?: string | null) => (policy === 'pol_grants' ? onGrants : onOffer)),
      save: vi.fn().mockResolvedValue(onGrants),
    };
    const levelsApi = fakeLevels(LEVELS, 'grant');
    const onPolicyChange = vi.fn();
    mounted = await mount(FeatureAccess, {
      workspaceId: 'ws1',
      api: api as unknown as FeatureAccessApi,
      levelsApi: levelsApi as never,
      onPolicyChange,
    });
    await mounted.flush();
    const picker = mounted.host.querySelector('select[data-field="policy"]') as HTMLSelectElement;
    expect([...picker.options].map((o) => o.textContent)).toEqual(['Alpha access', 'Analysts grants']);

    await mounted.select(picker, 'pol_grants');
    await mounted.flush();
    expect(api.read).toHaveBeenLastCalledWith('ws1', 'pol_grants');
    expect(levelsApi.read).toHaveBeenLastCalledWith('ws1', 'feature', 'pol_grants');
    expect(onPolicyChange).toHaveBeenCalledWith('pol_grants');
    expect(mounted.host.textContent).toContain('grants whoever holds it');

    await mounted.click(level(mounted, 'maps', 'read'));
    await mounted.click(saveButton(mounted));
    await mounted.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', [{ feature: 'maps', choice: 'everyone' }], 'pol_grants');
    expect(levelsApi.save).toHaveBeenCalledWith('ws1', 'feature', { 'feature:maps': 'read' }, 'pol_grants');

    // Back to the offer: the URL loses its policy.
    await mounted.select(mounted.host.querySelector('select[data-field="policy"]'), 'pol_access');
    expect(onPolicyChange).toHaveBeenLastCalledWith(null);
  });

  it('caps how far everyone goes with a feature offered here, saving the level alone', async () => {
    const api = fakeApi();
    api.read.mockResolvedValue(
      state([...BEFORE.features.filter((r) => r.key !== 'maps'), row({ key: 'maps', label: 'Maps', choice: 'everyone' })]),
    );
    const levelsApi = fakeLevels();
    const m = await render(api, levelsApi);
    expect(picked(m, 'maps')).toBe('write');
    // None denies the feature outright (its UseFeature too).
    expect(level(m, 'maps', 'none')?.getAttribute('title')).toContain('Denied');
    expect(at(m, 'maps', '[data-level-actions]')?.textContent).toContain('nexus:CreateView');

    await m.click(level(m, 'maps', 'read'));
    expect(m.host.textContent).toContain('1 unsaved change');
    await m.click(saveButton(m));
    await m.flush();
    expect(levelsApi.save).toHaveBeenCalledWith('ws1', 'feature', { 'feature:maps': 'read' }, null);
    expect(api.save).not.toHaveBeenCalled();
    expect(picked(m, 'maps')).toBe('read');
    expect(m.host.textContent).toContain('No unsaved change');
  });

  it('says so, read-only, when the access levels cannot be read', async () => {
    const levelsApi = { read: vi.fn().mockRejectedValue(new Error('down')), save: vi.fn() };
    const m = await render(fakeApi(), levelsApi);
    expect(m.host.textContent).toContain('Could not read the access levels');
    expect(at(m, 'chat', '[data-field="access"]')?.textContent).toBe('—');
  });

  it('on an organization (org:<id>), edits "<O> access": every feature listed, no link to a workspace page', async () => {
    const api = fakeApi();
    const m = await render(api, fakeLevels(), 'org:acme');
    expect(api.read).toHaveBeenCalledWith('org:acme', null);
    // Where features are taken out: even one not offered is listed.
    expect(m.host.querySelector('tr[data-feature="graph"]')).not.toBeNull();
    expect(m.host.querySelector('[data-action="configure"]')).toBeNull();
    expect(m.host.textContent).toContain('workspaces of this organization');
  });
});
