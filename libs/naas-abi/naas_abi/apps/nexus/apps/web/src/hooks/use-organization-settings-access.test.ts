// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { clearViewFlag, setViewFlag } from '@/lib/view-flag';
import {
  createOrganizationSettingsAccessStore,
  fetchOrganizationSettingsAccess,
  openableOrganizations,
  opensOrganizationSettings,
} from './use-organization-settings-access';

const IAM = { actions: { 'iam:ListPolicies': true } };
const NOTHING = { actions: { 'iam:ListPolicies': false } };

function fetcher(answers: Record<string, unknown>, seen: string[] = []) {
  return async (url: string) => {
    seen.push(url);
    if (!(url in answers)) return new Response('{}', { status: 403 });
    const answer = answers[url];
    if (answer instanceof Error) throw answer;
    return new Response(JSON.stringify(answer), { status: 200 });
  };
}

const ACCESS_ACME = `/api/iam/admin/access?scope=${encodeURIComponent('abi:nexus:organization/acme')}`;

describe('opensOrganizationSettings', () => {
  it('opens for an owner or admin of an organization', () => {
    expect(opensOrganizationSettings([{ role: 'owner', access: null }])).toBe(true);
    expect(opensOrganizationSettings([{ role: 'member', access: null }, { role: 'admin', access: null }])).toBe(true);
  });
  it('stays closed to a member holding no iam action there', () => {
    expect(opensOrganizationSettings([{ role: 'member', access: NOTHING }])).toBe(false);
  });
  it('opens to a member holding an iam action at the organization', () => {
    expect(opensOrganizationSettings([{ role: 'member', access: IAM }])).toBe(true);
  });
  it('stays closed when nothing is known', () => {
    expect(opensOrganizationSettings([])).toBe(false);
    expect(opensOrganizationSettings([{ role: null, access: null }])).toBe(false);
  });
});

const access = (org: string) =>
  `/api/iam/admin/access?scope=${encodeURIComponent(`abi:nexus:organization/${org}`)}`;

describe('fetchOrganizationSettingsAccess', () => {
  it('decides from the list alone when a role there is owner or admin', async () => {
    const seen: string[] = [];
    const opens = await fetchOrganizationSettingsAccess(
      fetcher(
        {
          '/api/organizations': [
            { id: 'acme', current_user_role: 'member' },
            { id: 'beta', current_user_role: 'admin' },
          ],
        },
        seen
      )
    );
    expect(opens).toBe(true);
    expect(seen).toEqual(['/api/organizations']);
  });
  it('a workspace owner who is a member of the organization gets nothing', async () => {
    const opens = await fetchOrganizationSettingsAccess(
      fetcher({
        '/api/organizations': [{ id: 'acme', current_user_role: 'member' }],
        [ACCESS_ACME]: NOTHING,
      })
    );
    expect(opens).toBe(false);
  });
  it('reads the access of every organization, in batches, with no cap', async () => {
    const orgs = Array.from({ length: 30 }, (_, i) => ({ id: `org-${i}`, current_user_role: 'member' }));
    const seen: string[] = [];
    const opens = await fetchOrganizationSettingsAccess(
      fetcher({ '/api/organizations': orgs, [access('org-29')]: IAM }, seen)
    );
    expect(opens).toBe(true);
    expect(seen.filter((url) => url.startsWith('/api/iam/admin/access'))).toHaveLength(30);
  });
  it('stops after the first batch that opens one', async () => {
    const orgs = Array.from({ length: 20 }, (_, i) => ({ id: `org-${i}`, current_user_role: null }));
    const seen: string[] = [];
    const opens = await fetchOrganizationSettingsAccess(
      fetcher({ '/api/organizations': orgs, [access('org-3')]: IAM }, seen)
    );
    expect(opens).toBe(true);
    expect(seen.filter((url) => url.startsWith('/api/iam/admin/access'))).toHaveLength(8);
  });
});

describe('openableOrganizations (the /organizations picker)', () => {
  it('keeps owners\' and admins\' organizations and those whose access opens, in order', async () => {
    const seen: string[] = [];
    const orgs = [
      { id: 'acme', currentUserRole: 'admin' },
      { id: 'beta', currentUserRole: 'member' },
      { id: 'gamma', currentUserRole: 'member' },
    ];
    const opened = await openableOrganizations(orgs, fetcher({ [access('gamma')]: IAM }, seen));
    expect(opened.map((org) => org.id)).toEqual(['acme', 'gamma']);
    expect(seen).toEqual([access('beta'), access('gamma')]);
  });
});

describe('the store', () => {
  it('shares one request per user, and a failure keeps the last answer', async () => {
    let calls = 0;
    let fail = false;
    const store = createOrganizationSettingsAccessStore(async (url) => {
      if (url === '/api/organizations') {
        calls += 1;
        if (fail) throw new Error('down');
        return new Response(JSON.stringify([{ id: 'acme', current_user_role: 'admin' }]), { status: 200 });
      }
      return new Response('{}', { status: 403 });
    });
    await Promise.all([store.getState().load('olivia'), store.getState().load('olivia')]);
    expect(calls).toBe(1);
    expect(store.getState()).toMatchObject({ status: 'ready', opens: true });
    fail = true;
    await store.getState().load('olivia');
    expect(store.getState()).toMatchObject({ status: 'ready', opens: true });
    await store.getState().load('bob');
    expect(store.getState()).toMatchObject({ status: 'error', opens: null, userId: 'bob' });
  });
});

describe('in a view', () => {
  afterEach(() => clearViewFlag());

  it('never asks: the organizations\' pages are not part of a view, so none opens', async () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, Date.now() + 15 * 60_000);
    const seen: string[] = [];
    const answers = { '/api/organizations': [{ id: 'acme', current_user_role: 'admin' }], [ACCESS_ACME]: IAM };
    expect(await fetchOrganizationSettingsAccess(fetcher(answers, seen))).toBe(false);
    expect(await openableOrganizations([{ id: 'acme', currentUserRole: 'admin' }], fetcher(answers, seen))).toEqual([]);
    expect(seen).toEqual([]);
  });
});
