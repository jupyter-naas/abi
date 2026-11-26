// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessApi } from './feature-access-api';
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

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(api: ReturnType<typeof fakeApi>) {
  mounted = await mount(FeatureAccess, { workspaceId: 'ws1', api: api as unknown as FeatureAccessApi });
  await mounted.flush();
  return mounted;
}

const at = (m: Mounted, feature: string, selector: string) =>
  m.host.querySelector(`tr[data-feature="${feature}"] ${selector}`) as HTMLButtonElement | null;
const saveButton = (m: Mounted) => m.host.querySelector('[data-action="save"]') as HTMLButtonElement;

describe('FeatureAccess', () => {
  it('shows each feature, the Nexus Files one included, with its choice and the other policies granting it', async () => {
    const m = await render(fakeApi());

    expect([...m.host.querySelectorAll('tr[data-feature]')].map((tr) => tr.getAttribute('data-feature'))).toEqual([
      'chat',
      'files',
      'graph',
      'maps',
      'marketplace',
      'search',
    ]);
    expect(m.host.querySelector('a[href="/workspace/ws1/settings/files"]')?.textContent).toBe('Files');
    expect(at(m, 'chat', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
    expect(at(m, 'chat', '[data-effect="Allow"]')?.textContent).toBe('Also granted by Chat + Files');
    expect(at(m, 'maps', '[data-effect="Allow"] a')?.getAttribute('href')).toContain('pol_cf');
    expect(at(m, 'marketplace', '[data-effect="Allow"]')?.textContent).toBe(
      'Also granted by Marketplace (attached nowhere)',
    );
    expect(m.host.textContent).not.toContain('Roles & permissions');
    expect(m.host.textContent).toContain('admins included');
    expect(m.host.textContent).not.toContain('Platform admins see every feature');
    // Features are the workspace's offer: the description links to "<W> access".
    expect(m.host.querySelector('a[href*="pol_access"]')?.textContent).toBe('Alpha access');
    expect(m.host.querySelector('[data-choice="only"]')).toBeNull();
    expect(saveButton(m).disabled).toBe(true);
  });

  it('makes a hand-edited row read-only with a link, and a feature not offered Nobody-only', async () => {
    const m = await render(fakeApi());

    const search = ['everyone', 'nobody'].map((c) => at(m, 'search', `[data-choice="${c}"]`)?.disabled);
    expect(search).toEqual([true, true]);
    expect(at(m, 'search', '.workspace-features-note')?.textContent).toContain('read-only here');
    expect(at(m, 'search', '.workspace-features-note a')?.getAttribute('href')).toContain('pol_search');

    const graph = ['everyone', 'nobody'].map((c) => at(m, 'graph', `[data-choice="${c}"]`)?.disabled);
    expect(graph).toEqual([true, false]);
    expect(at(m, 'graph', '.workspace-features-note')?.textContent).toContain('Not offered in this workspace');
    expect(at(m, 'graph', '.workspace-features-note a')?.textContent).toBe('Widen Alpha access');
  });

  it('saves several changes in one step and keeps the refused one as a draft', async () => {
    const after = state(
      [
        ...BEFORE.features.filter((r) => r.key !== 'maps'),
        row({ key: 'maps', label: 'Maps', choice: 'everyone', also: [CHAT_FILES] }),
      ],
      { marketplace: 'IAM refused the attachment.' },
    );
    const api = fakeApi(after);
    const m = await render(api);

    await m.click(at(m, 'maps', '[data-choice="everyone"]'));
    await m.click(at(m, 'marketplace', '[data-choice="everyone"]'));
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
    expect(at(m, 'maps', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
    expect(at(m, 'marketplace', '[role="alert"]')?.textContent).toBe('IAM refused the attachment.');
    expect(at(m, 'marketplace', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
    expect(m.host.textContent).toContain('1 unsaved change');
  });

  it('lays the features out as Users: a count, a search that narrows the table, columns that sort', async () => {
    const m = await render(fakeApi());
    const keys = () => [...m.host.querySelectorAll('tr[data-feature]')].map((tr) => tr.getAttribute('data-feature'));

    expect(m.host.textContent).toContain('2 offered · 4 not offered');
    expect(m.host.textContent).toContain('6 features');
    await m.click(m.host.querySelector('[data-sort="offered"]'));
    expect(keys()).toEqual(['chat', 'search', 'files', 'graph', 'maps', 'marketplace']);

    await m.type(m.host.querySelector('input[type="search"], input') as HTMLInputElement, 'not offered');
    expect(keys()).toEqual(['graph']);
    expect(m.host.textContent).toContain('1 of 6 features');
    await m.click(m.host.querySelector('[data-action="clear-filters"]'));
    expect(keys()).toHaveLength(6);
  });

  it('discards the drafts', async () => {
    const api = fakeApi();
    const m = await render(api);

    await m.click(at(m, 'chat', '[data-choice="nobody"]'));
    expect(m.host.textContent).toContain('1 unsaved change');
    await m.click(m.host.querySelector('[data-action="discard"]'));
    expect(at(m, 'chat', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
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
    const onPolicyChange = vi.fn();
    mounted = await mount(FeatureAccess, {
      workspaceId: 'ws1',
      api: api as unknown as FeatureAccessApi,
      onPolicyChange,
    });
    await mounted.flush();
    const picker = mounted.host.querySelector('select[data-field="policy"]') as HTMLSelectElement;
    expect([...picker.options].map((o) => o.textContent)).toEqual(['Alpha access', 'Analysts grants']);
    expect(at(mounted, 'chat', '[data-choice="everyone"]')?.textContent).toBe('Everyone');

    await mounted.select(picker, 'pol_grants');
    await mounted.flush();
    expect(api.read).toHaveBeenLastCalledWith('ws1', 'pol_grants');
    expect(onPolicyChange).toHaveBeenCalledWith('pol_grants');
    expect(at(mounted, 'chat', '[data-choice="everyone"]')?.textContent).toBe('Granted');
    expect(mounted.host.textContent).toContain('grants whoever holds it');

    await mounted.click(at(mounted, 'maps', '[data-choice="everyone"]'));
    await mounted.click(saveButton(mounted));
    await mounted.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', [{ feature: 'maps', choice: 'everyone' }], 'pol_grants');

    // Back to the offer: the URL loses its policy.
    await mounted.select(mounted.host.querySelector('select[data-field="policy"]'), 'pol_access');
    expect(onPolicyChange).toHaveBeenLastCalledWith(null);
  });

  it('caps how far everyone goes with a feature (Access), saved with the rest', async () => {
    const graphLevel = {
      key: 'feature:graph',
      kind: 'feature' as const,
      name: 'graph',
      label: 'Graph',
      level: 'write' as const,
      choices: ['none', 'read', 'write'] as ('none' | 'read' | 'write')[],
      actions: { read: ['nexus:GetView'], write: ['nexus:CreateView'] },
    };
    const levelsState = {
      workspace_id: 'ws1',
      kind: 'feature' as const,
      mode: 'cap' as const,
      access_policy: null,
      policy: null,
      policies: [],
      editable: true,
      reason: null,
      rows: [graphLevel],
    };
    const levelsApi = {
      read: vi.fn().mockResolvedValue(levelsState),
      save: vi.fn().mockResolvedValue({ ...levelsState, rows: [{ ...graphLevel, level: 'read' }] }),
    };
    const api = fakeApi();
    mounted = await mount(FeatureAccess, {
      workspaceId: 'ws1',
      api: api as unknown as FeatureAccessApi,
      levelsApi: levelsApi as never,
    });
    await mounted.flush();
    const level = (value: string) => at(mounted!, 'graph', `[data-access-level] [data-level="${value}"]`);
    expect(level('write')?.getAttribute('aria-checked')).toBe('true');
    // On the offer, None is the feature's Nobody: not offered twice.
    expect(level('none')).toBeNull();
    expect(at(mounted, 'graph', '[data-level-actions]')?.textContent).toContain('nexus:CreateView');
    expect(at(mounted, 'chat', '[data-field="access"]')?.textContent).toBe('—');

    await mounted.click(level('read'));
    expect(mounted.host.textContent).toContain('1 unsaved change');
    await mounted.click(saveButton(mounted));
    await mounted.flush();
    expect(levelsApi.save).toHaveBeenCalledWith('ws1', 'feature', { 'feature:graph': 'read' }, null);
    expect(api.save).not.toHaveBeenCalled();
    expect(level('read')?.getAttribute('aria-checked')).toBe('true');
    expect(mounted.host.textContent).toContain('No unsaved change');
  });
});
