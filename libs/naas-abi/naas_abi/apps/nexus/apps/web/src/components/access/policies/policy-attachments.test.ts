// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import { mount, type Mounted } from '@/lib/testing/mount';
import { ORG, WS, attachment, fakeApi, readerPolicy, wsScope } from '../access-fixtures';
import { principal } from '../service-fixtures';
import { PolicyAttachments } from './policy-attachments';
import { PolicyEditor } from './policy-editor';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const g = principal({ id: 'grp_g', kind: 'group', name: 'G', display_name: null, email: null });
const bob = principal({ id: 'usr_bob', display_name: 'Bob' });
const toGroup = attachment({ id: 'a_g', policy_id: 'pol_w', principal_id: g.id, principal: g, scope: WS });
const toBob = attachment({ id: 'a_b', policy_id: 'pol_w', principal_id: bob.id, principal: bob, scope: `${ORG}/*` });

function api(over: Record<string, unknown> = {}) {
  return fakeApi({
    listAttachments: vi.fn().mockResolvedValue({ items: [toGroup, toBob] }),
    resources: vi.fn(({ scope }: { scope: string }) =>
      Promise.resolve({ items: scope === ORG ? [{ name: ORG, id: 'acme', label: 'Acme', description: '' }] : [] }),
    ),
    access: vi.fn((scope?: string) => Promise.resolve({ actions: { 'iam:DetachPolicy': scope === WS } })),
    detach: vi.fn().mockResolvedValue(undefined),
    ...over,
  });
}

const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;

describe('Where a policy is attached', () => {
  it('lists to whom and at which level, each opening their page, with the detach where IAM allows it', async () => {
    const client = api();
    const open = { person: vi.fn(), group: vi.fn() };
    mounted = await mount(PolicyAttachments, { api: client, policyId: 'pol_w', here: 'abi:', can: () => false, open });
    await mounted.flush();
    await mounted.flush();

    expect(client.listAttachments).toHaveBeenCalledWith({ policy_id: 'pol_w' });
    const rows = [...document.querySelectorAll('[data-attached]')];
    expect(rows.map((r) => r.getAttribute('data-attached'))).toEqual(['usr_bob', 'grp_g']);
    expect(rows[0].textContent).toContain('Organization Acme, and all below it');
    expect(rows[1].textContent).toContain('Workspace ws-1 (Acme)');
    expect(rows[1].textContent).toContain('group');

    await mounted.click(button('G') ?? null);
    expect(open.group).toHaveBeenCalledWith('grp_g', 'G');
    await mounted.click(button('Bob') ?? null);
    expect(open.person).toHaveBeenCalledWith('usr_bob', 'Bob');

    expect(field('Detach from Bob at Organization Acme, and all below it')).toBeNull();
    await mounted.click(field('Detach from G at Workspace ws-1 (Acme)'));
    await mounted.click(button('Confirm detach') ?? null);
    expect(client.detach).toHaveBeenCalledWith({ policy_id: 'pol_w', principal_id: 'grp_g', scope: WS });
  });

  it('says so when IAM lets the caller list none of it', async () => {
    const client = api({ listAttachments: vi.fn().mockRejectedValue(new IamAdminError('You do not have permission to do this.', 403)) });
    mounted = await mount(PolicyAttachments, { api: client, policyId: 'pol_w', here: 'abi:', can: () => false });
    await mounted.flush();
    expect(mounted.host.textContent).toContain('You may not list where it is attached.');
    expect(document.querySelector('[role="alert"]')).toBeNull();
  });

  it('never detaches a role by hand: a role is a membership', async () => {
    const role = attachment({ id: 'a_r', policy_id: 'builtin.member', principal_id: bob.id, principal: bob, scope: WS });
    const client = api({ listAttachments: vi.fn().mockResolvedValue({ items: [role] }) });
    mounted = await mount(PolicyAttachments, { api: client, policyId: 'builtin.member', here: WS, can: () => true });
    await mounted.flush();
    expect(document.querySelector('[data-attached="usr_bob"]')).not.toBeNull();
    expect(document.querySelector('[aria-label^="Detach"]')).toBeNull();
  });

  it('is part of the policy’s page in the editor', async () => {
    const client = api({
      publishers: vi.fn().mockResolvedValue({ scope: WS, publishers: [] }),
      getPolicy: vi.fn().mockResolvedValue({ ...readerPolicy, sub_policies: [] }),
      validatePolicy: vi.fn().mockResolvedValue({ valid: true, errors: [], document: readerPolicy.document }),
    });
    mounted = await mount(PolicyEditor, {
      api: client,
      policy: readerPolicy,
      scope: wsScope,
      can: () => true,
      onSaved: vi.fn(),
      onCancel: vi.fn(),
      validationDelayMs: 0,
    });
    await mounted.flush();
    await mounted.flush();
    expect(document.querySelector('[aria-label="Where it is attached"]')).not.toBeNull();
    expect(client.listAttachments).toHaveBeenCalledWith({ policy_id: 'pol_1' });
  });
});
