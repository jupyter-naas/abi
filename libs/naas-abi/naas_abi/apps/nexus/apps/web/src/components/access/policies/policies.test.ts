// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { PolicyDocument } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { EMPTY_DIRECTORY } from '../access-directory';
import { PLATFORM_ACCESS_SCOPE, type AccessScope } from '../access-scope';
import {
  adminGrantable,
  catalogsView,
  fakeApi,
  managedPolicy,
  moduleScopesView,
  readerPolicy,
  wsScope,
} from '../access-fixtures';
import { PoliciesView } from './policies';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
/** Past the editor's validation delay, so IAM has answered. */
const validated = async () => {
  await new Promise((resolve) => setTimeout(resolve, 400));
  await mounted!.flush();
};

function fake(over: Record<string, unknown> = {}) {
  return fakeApi({
    listPolicies: vi.fn().mockResolvedValue({ items: [managedPolicy, readerPolicy], next_after: null }),
    catalogs: vi.fn().mockResolvedValue(catalogsView),
    grantable: vi.fn().mockResolvedValue(adminGrantable),
    moduleScopes: vi.fn().mockResolvedValue(moduleScopesView),
    validatePolicy: vi.fn((source: { document: PolicyDocument }) =>
      Promise.resolve({ valid: true, errors: [], document: source.document }),
    ),
    ...over,
  });
}

async function open(can: (a: string) => boolean, over: Record<string, unknown> = {}, scope: AccessScope = PLATFORM_ACCESS_SCOPE) {
  const api = fake(over);
  mounted = await mount(PoliciesView, { api, can, scope, directory: EMPTY_DIRECTORY });
  await mounted.flush();
  return api;
}

describe('PoliciesView', () => {
  it('lists policies and marks the managed ones', async () => {
    await open(() => true);
    const managed = document.querySelector('[data-policy="builtin.viewer"]');
    expect(managed?.textContent).toContain('managed');
    expect(document.querySelector('[data-policy="pol_1"]')?.textContent).toContain('Graph reader');
    expect(document.querySelector('[aria-label="Delete Viewer"]')).toBeNull();
    expect(document.querySelector('[aria-label="Delete Graph reader"]')).not.toBeNull();
  });

  it('opens a managed policy read-only', async () => {
    await open(() => true);
    await mounted!.click(document.querySelector('[data-policy="builtin.viewer"] button'));
    expect(mounted!.host.textContent).toContain('Managed: IAM writes this policy');
    expect(button('Save changes')).toBeUndefined();
  });

  it('asks before deleting, then deletes and reloads', async () => {
    const deletePolicy = vi.fn().mockResolvedValue(undefined);
    await open(() => true, { deletePolicy });
    await mounted!.click(document.querySelector('[aria-label="Delete Graph reader"]'));
    expect(deletePolicy).not.toHaveBeenCalled();
    await mounted!.click(button('Confirm delete') ?? null);
    expect(deletePolicy).toHaveBeenCalledWith('pol_1');
  });

  it('shows no create or delete to a caller who may not', async () => {
    const api = await open((action) => action === 'iam:ListPolicies');
    expect(button('New policy')).toBeUndefined();
    expect(document.querySelector('[aria-label="Delete Graph reader"]')).toBeNull();
    await mounted!.click(document.querySelector('[data-policy="pol_1"] button'));
    expect(button('Save changes')).toBeUndefined();
    expect(mounted!.host.textContent).toContain('Read only');
    expect(api.grantable).not.toHaveBeenCalled();
  });

  it('says why the list could not load', async () => {
    await open(() => true, { listPolicies: vi.fn().mockRejectedValue(new Error('You do not have permission')) });
    expect(mounted!.host.textContent).toContain('You do not have permission');
  });
});

describe('PoliciesView at a workspace', () => {
  const owned = { ...readerPolicy, id: 'pol_ws', name: 'Recruiters', owner_scope: 'abi:acme:ws-1' };
  const fromOrg = { ...readerPolicy, id: 'pol_org', name: 'Org readers', owner_scope: 'abi:acme:-' };
  const listed = { listPolicies: vi.fn().mockResolvedValue({ items: [owned, fromOrg], next_after: null }) };

  it('lists the level’s own and, read-only, those it may attach from above', async () => {
    const api = await open(() => true, listed, wsScope);
    expect(api.listPolicies).toHaveBeenCalledWith(undefined, 'abi:acme:ws-1');
    expect(document.querySelector('[data-policy="pol_org"]')?.textContent).toContain('Organization acme');
    expect(document.querySelector('[aria-label="Delete Org readers"]')).toBeNull();
    expect(document.querySelector('[aria-label="Delete Recruiters"]')).not.toBeNull();
    await mounted!.click(document.querySelector('[data-policy="pol_org"] button'));
    expect(mounted!.host.textContent).toContain('Read only');
  });

  it('builds a policy from what the caller may grant, owned by the workspace', async () => {
    const createPolicy = vi.fn((input: { document: PolicyDocument }) =>
      Promise.resolve({ ...owned, document: input.document }),
    );
    const api = await open(() => true, { ...listed, createPolicy }, wsScope);
    expect(api.grantable).toHaveBeenCalledWith('abi:acme:ws-1');
    expect(api.moduleScopes).toHaveBeenCalledWith({ workspace_id: 'ws-1' });

    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    // Only what the set and the caller allow: acme.people's agents and the chat feature.
    expect(document.querySelector('[data-builder-group="acme.market"]')).toBeNull();
    expect(field('acme.people: Recruiter')).not.toBeNull();
    expect(field('Nexus features: Chat')).not.toBeNull();

    await mounted!.type(field('Policy name'), 'Recruiters');
    await mounted!.click(field('acme.people: Recruiter'));
    await validated();
    expect(api.validatePolicy).toHaveBeenLastCalledWith(expect.anything(), 'abi:acme:ws-1');
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();

    expect(createPolicy).toHaveBeenCalledWith({
      document: {
        version: '2026-10-13',
        statements: [
          { sid: 'UseAgent', effect: 'Allow', actions: ['module:UseAgent'], resources: ['${scope}:module:agent/acme.people/Recruiter'] },
        ],
      },
      name: 'Recruiters',
      description: '',
      scope: 'abi:acme:ws-1',
    });
  });

  it('shows IAM’s refusal beside the item it names', async () => {
    const refusal =
      'You cannot grant what you do not hold: statement 0 (UseAgent) allows module:UseAgent on ${scope}:module:agent/acme.people/Coach at abi:acme:ws-1, and you do not hold it there';
    const createPolicy = vi.fn().mockRejectedValue(new IamAdminError(refusal, 403));
    await open(() => true, { ...listed, createPolicy }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    await mounted!.type(field('Policy name'), 'Coaches');
    await mounted!.click(field('acme.people: Coach'));
    await validated();
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();

    const item = document.querySelector('[data-builder-item="module:agent/acme.people/Coach"]');
    expect(item?.querySelector('[role="alert"]')?.textContent).toBe(refusal);
    expect(document.querySelector('[data-builder-item="module:agent/acme.people/Recruiter"] [role="alert"]')).toBeNull();
  });

  it('starts from a built-in role', async () => {
    const member = {
      ...managedPolicy,
      id: 'builtin.member',
      document: { version: '2026-10-13', statements: [{ effect: 'Allow' as const, actions: ['nexus:ListFiles'], resources: ['${scope}:nexus:file/*'] }] },
    };
    const getPolicy = vi.fn().mockResolvedValue(member);
    await open(() => true, { ...listed, getPolicy }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    const start = field('Start from a built-in role') as HTMLSelectElement;
    start.value = 'builtin.member';
    start.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();

    expect(getPolicy).toHaveBeenCalledWith('builtin.member');
    expect(mounted!.host.textContent).toContain('1 other statement stays as written');
  });
});
