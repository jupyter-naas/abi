// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { InviteProviders } from '@/lib/invitations';
import { mount, type Mounted } from '../../system-render';
import { allowAll, fakeApi, group, principal } from '../service-fixtures';
import { GroupsView } from './groups';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const buttonNamed = (label: string) =>
  [...document.querySelectorAll('button')].find(
    (b) => b.textContent?.trim() === label || b.getAttribute('aria-label') === label,
  ) ?? null;

const providers: InviteProviders = {
  enabled: true,
  default_provider: 'okta',
  providers: [{ name: 'okta', display_name: 'Okta', provisioning: 'none', managed_in_provider: true }],
};

function setup() {
  const detail = group({ members: [principal({ id: 'usr_9', display_name: 'Bob' })] });
  return fakeApi({
    listGroups: vi.fn(() => Promise.resolve({ items: [detail] })),
    getGroup: vi.fn(() => Promise.resolve(detail)),
    listPrincipals: vi.fn(() => Promise.resolve({ items: [principal()], next_after: null })),
    addMember: vi.fn(() => Promise.resolve(detail)),
    removeMember: vi.fn(() => Promise.resolve(detail)),
    mapIdpGroup: vi.fn(() => Promise.resolve(detail)),
    unmapIdpGroup: vi.fn(() => Promise.resolve(detail)),
  });
}

async function open(api: ReturnType<typeof setup>, can: (a: string) => boolean = allowAll) {
  mounted = await mount(GroupsView, { api, can, loadProviders: () => Promise.resolve(providers) });
  await mounted.flush();
  await mounted.click(document.querySelector('[data-group] button.system-row-toggle'));
  await mounted.flush();
}

describe('GroupsView', () => {
  it('lists groups with their member count', async () => {
    mounted = await mount(GroupsView, { api: setup(), can: allowAll, loadProviders: () => Promise.resolve(providers) });
    await mounted.flush();
    const row = document.querySelector('[data-group="grp_1"]');
    expect(row?.textContent).toContain('Analysts');
    expect(row?.textContent).toContain('platform');
    expect(row?.querySelector('.system-num')?.textContent).toBe('1');
  });

  it('adds a member by id', async () => {
    const api = setup();
    await open(api);
    await mounted!.type(document.querySelector('[aria-label="Member id"]'), 'usr_1');
    await mounted!.click(buttonNamed('Add member'));
    expect(api.addMember).toHaveBeenCalledWith('grp_1', 'usr_1');
  });

  it('removes a member', async () => {
    const api = setup();
    await open(api);
    await mounted!.click(buttonNamed('Remove Bob'));
    expect(api.removeMember).toHaveBeenCalledWith('grp_1', 'usr_9');
  });

  it('maps an IdP group claim from a provider', async () => {
    const api = setup();
    await open(api);
    await mounted!.type(document.querySelector('[aria-label="Group claim value"]'), 'eng-admins');
    await mounted!.click(buttonNamed('Map group'));
    expect(api.mapIdpGroup).toHaveBeenCalledWith('grp_1', { provider: 'okta', claim_value: 'eng-admins' });
  });

  it('shows no write controls without the rights', async () => {
    const api = setup();
    await open(api, () => false);
    expect(buttonNamed('Add member')).toBeNull();
    expect(buttonNamed('Map group')).toBeNull();
    expect(buttonNamed('Remove Bob')).toBeNull();
    expect(buttonNamed('Create group')).toBeNull();
    expect(buttonNamed('Delete Analysts')).toBeNull();
  });
});
