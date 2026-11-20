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
    candidates: vi.fn().mockResolvedValue([
      { id: 'usr_ann', kind: 'user', name: 'Ann' },
      { id: 'grp_ops', kind: 'group', name: 'Ops' },
    ]),
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
const saveButton = (m: Mounted) => m.host.querySelector('.workspace-features-save') as HTMLButtonElement;

describe('FeatureAccess', () => {
  it('shows each feature with its choice and the other policies granting it', async () => {
    const m = await render(fakeApi());

    expect([...m.host.querySelectorAll('tr[data-feature]')].map((tr) => tr.getAttribute('data-feature'))).toEqual([
      'chat',
      'files',
      'graph',
      'marketplace',
      'search',
    ]);
    expect(at(m, 'chat', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
    expect(at(m, 'chat', '[data-effect="Allow"]')?.textContent).toBe('Also granted by Chat + Files');
    expect(at(m, 'files', '[data-effect="Allow"] a')?.getAttribute('href')).toContain('pol_cf');
    expect(at(m, 'marketplace', '[data-effect="Allow"]')?.textContent).toBe(
      'Also granted by Marketplace (attached nowhere)',
    );
    expect(m.host.textContent).not.toContain('Roles & permissions');
    expect(m.host.textContent).toContain('Platform administrators see every feature');
    expect(saveButton(m).disabled).toBe(true);
  });

  it('makes a hand-edited row read-only with a link, and a feature not offered Nobody-only', async () => {
    const m = await render(fakeApi());

    const search = ['everyone', 'only', 'nobody'].map((c) => at(m, 'search', `[data-choice="${c}"]`)?.disabled);
    expect(search).toEqual([true, true, true]);
    expect(at(m, 'search', '.workspace-features-note')?.textContent).toContain('read-only here');
    expect(at(m, 'search', '.workspace-features-note a')?.getAttribute('href')).toContain('pol_search');

    const graph = ['everyone', 'only', 'nobody'].map((c) => at(m, 'graph', `[data-choice="${c}"]`)?.disabled);
    expect(graph).toEqual([true, true, false]);
    expect(at(m, 'graph', '.workspace-features-note')?.textContent).toContain('Not offered in this workspace');
    expect(at(m, 'graph', '.workspace-features-note a')?.textContent).toBe('Widen Alpha access');
  });

  it('saves several changes in one step and keeps the refused one as a draft', async () => {
    const after = state(
      [
        ...BEFORE.features.filter((r) => r.key !== 'files'),
        row({ key: 'files', label: 'Files', choice: 'everyone', also: [CHAT_FILES] }),
      ],
      { marketplace: 'IAM refused the attachment.' },
    );
    const api = fakeApi(after);
    const m = await render(api);

    await m.click(at(m, 'files', '[data-choice="everyone"]'));
    await m.click(at(m, 'marketplace', '[data-choice="only"]'));
    await m.flush();
    expect(api.candidates).toHaveBeenCalledWith('ws1', SCOPE);
    expect(saveButton(m).disabled).toBe(true);
    expect(at(m, 'marketplace', '.workspace-features-note')?.textContent).toBe('Choose who may use Marketplace.');

    await m.select(at(m, 'marketplace', 'select'), 'usr_ann');
    expect(at(m, 'marketplace', '[data-principal="usr_ann"]')?.textContent).toContain('Ann');
    expect(m.host.textContent).toContain('2 unsaved changes');

    await m.click(saveButton(m));
    await m.flush();
    expect(api.save).toHaveBeenCalledTimes(1);
    expect(api.save).toHaveBeenCalledWith('ws1', [
      { feature: 'files', choice: 'everyone' },
      { feature: 'marketplace', choice: 'only', principals: ['usr_ann'] },
    ]);
    expect(at(m, 'files', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
    expect(at(m, 'marketplace', '[role="alert"]')?.textContent).toBe('IAM refused the attachment.');
    expect(at(m, 'marketplace', '[data-choice="only"]')?.getAttribute('aria-checked')).toBe('true');
    expect(m.host.textContent).toContain('1 unsaved change');
  });

  it('discards the drafts', async () => {
    const api = fakeApi();
    const m = await render(api);

    await m.click(at(m, 'chat', '[data-choice="nobody"]'));
    expect(m.host.textContent).toContain('1 unsaved change');
    await m.click(m.host.querySelector('.workspace-features-discard'));
    expect(at(m, 'chat', '[data-choice="everyone"]')?.getAttribute('aria-checked')).toBe('true');
    expect(m.host.textContent).toContain('No unsaved change');
    expect(api.save).not.toHaveBeenCalled();
  });
});
