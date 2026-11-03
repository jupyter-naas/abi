import { describe, expect, it } from 'vitest';
import {
  createOrganizationSettingsAccessStore,
  fetchOrganizationSettingsAccess,
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

describe('fetchOrganizationSettingsAccess', () => {
  it('asks the access only when the role does not open it, and stops at the first that does', async () => {
    const seen: string[] = [];
    const opens = await fetchOrganizationSettingsAccess(
      fetcher(
        {
          '/api/organizations': [{ id: 'acme' }, { id: 'beta' }, { id: 'gamma' }],
          '/api/organizations/acme': { current_user_role: 'member' },
          [ACCESS_ACME]: NOTHING,
          '/api/organizations/beta': { current_user_role: 'admin' },
        },
        seen
      )
    );
    expect(opens).toBe(true);
    expect(seen).toEqual(['/api/organizations', '/api/organizations/acme', ACCESS_ACME, '/api/organizations/beta']);
  });
  it('a workspace owner who is a member of the organization gets nothing', async () => {
    const opens = await fetchOrganizationSettingsAccess(
      fetcher({
        '/api/organizations': [{ id: 'acme' }],
        '/api/organizations/acme': { current_user_role: 'member' },
        [ACCESS_ACME]: NOTHING,
      })
    );
    expect(opens).toBe(false);
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
        return new Response(JSON.stringify([{ id: 'acme' }]), { status: 200 });
      }
      return new Response(JSON.stringify({ current_user_role: 'admin' }), { status: 200 });
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
