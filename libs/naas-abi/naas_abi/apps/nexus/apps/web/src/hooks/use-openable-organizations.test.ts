import { describe, expect, it } from 'vitest';
import {
  createOpenableOrganizationsStore,
  needsOpenableOrganizations,
  OPENABLE_ORGANIZATIONS_TTL_MS,
} from './use-openable-organizations';

const ACCESS = '/api/iam/admin/access?scope=';

function api(answers: Record<string, unknown>, calls: string[]) {
  return async (url: string) => {
    calls.push(url);
    const key = url.startsWith(ACCESS) ? decodeURIComponent(url.slice(ACCESS.length)) : url;
    if (!(key in answers)) return new Response('{}', { status: 403 });
    const answer = answers[key];
    if (answer instanceof Error) throw answer;
    return new Response(JSON.stringify(answer), { status: 200 });
  };
}

const LIST = [
  { id: 'acme', name: 'Acme', current_user_role: 'admin' },
  { id: 'beta', name: 'Beta', current_user_role: 'member' },
];

describe('the openable organizations store', () => {
  it('asks once for callers that load at the same time', async () => {
    const calls: string[] = [];
    const store = createOpenableOrganizationsStore(api({ '/api/organizations': LIST }, calls));
    await Promise.all([store.getState().load('u1'), store.getState().load('u1'), store.getState().load('u1')]);
    expect(calls.filter((c) => c === '/api/organizations')).toHaveLength(1);
    expect(store.getState()).toMatchObject({ status: 'ready', orgs: [{ id: 'acme', name: 'Acme' }] });
  });

  it('reads the access only of the organizations the role does not open', async () => {
    const calls: string[] = [];
    const store = createOpenableOrganizationsStore(
      api(
        {
          '/api/organizations': LIST,
          'abi:nexus:organization/beta': { actions: { 'iam:ListPolicies': true } },
        },
        calls
      )
    );
    await store.getState().load('u1');
    expect(calls.filter((c) => c.startsWith(ACCESS))).toHaveLength(1);
  });

  it('keeps the last list of this user when a read fails', async () => {
    const answers: Record<string, unknown> = { '/api/organizations': LIST };
    const store = createOpenableOrganizationsStore(api(answers, []));
    await store.getState().load('u1');
    answers['/api/organizations'] = new Error('offline');
    await store.getState().load('u1');
    expect(store.getState()).toMatchObject({ status: 'ready', orgs: [{ id: 'acme', name: 'Acme' }] });
  });

  it('is an error with no earlier list', async () => {
    const store = createOpenableOrganizationsStore(api({ '/api/organizations': new Error('offline') }, []));
    await store.getState().load('u1');
    expect(store.getState().status).toBe('error');
  });

  it('starts over for another user', async () => {
    const store = createOpenableOrganizationsStore(api({ '/api/organizations': LIST }, []));
    await store.getState().load('u1');
    const next = store.getState().load('u2');
    expect(store.getState()).toMatchObject({ userId: 'u2', status: 'checking', orgs: null });
    await next;
  });
});

describe('needsOpenableOrganizations', () => {
  const ready = { userId: 'u1', status: 'ready' as const, loadedAt: 1_000, pending: null };

  it('reads for a new user, after an error, or once the list is stale', () => {
    expect(needsOpenableOrganizations(ready, 'u2', 1_000)).toBe(true);
    expect(needsOpenableOrganizations({ ...ready, status: 'error' }, 'u1', 1_000)).toBe(true);
    expect(needsOpenableOrganizations(ready, 'u1', 1_000 + OPENABLE_ORGANIZATIONS_TTL_MS + 1)).toBe(true);
  });

  it('does not read again while fresh or while a read is in flight', () => {
    expect(needsOpenableOrganizations(ready, 'u1', 1_000 + 5_000)).toBe(false);
    const pending = { userId: 'u2', promise: Promise.resolve() };
    expect(needsOpenableOrganizations({ ...ready, pending }, 'u2', 1_000)).toBe(false);
  });
});
