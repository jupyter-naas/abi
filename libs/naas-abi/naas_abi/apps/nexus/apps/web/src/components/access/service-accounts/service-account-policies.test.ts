// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PolicyView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { readerPolicy } from '../access-fixtures';
import { allowAll, fakeApi } from '../service-fixtures';
import { ServiceAccountPolicies } from './service-accounts';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const policy = (id: string, name: string): PolicyView => ({ ...readerPolicy, id, name, managed: true });

const ALL = [
  policy('builtin.api', 'Nexus API'),
  policy('builtin.engine', 'Engine'),
  policy('builtin.job', 'Engine job'),
  policy('builtin.idp', 'Built-in IdP'),
  policy('builtin.module_bootstrap', 'Module bootstrap'),
  policy('module.acme.people', 'Module acme/people'),
  policy('builtin.platform.member', 'Platform member'),
  policy('builtin.viewer', 'Viewer'),
  readerPolicy,
];

describe('Platform › Service accounts: their policies', () => {
  it('lists only the service accounts’ policies, read-only, across pages', async () => {
    const listPolicies = vi
      .fn()
      .mockResolvedValueOnce({ items: ALL.slice(0, 4), next_after: 'p2' })
      .mockResolvedValueOnce({ items: ALL.slice(4), next_after: null });
    mounted = await mount(ServiceAccountPolicies, { api: fakeApi({ listPolicies }), can: allowAll });
    await mounted.flush();
    await mounted.flush();
    const rows = [...document.querySelectorAll('[data-sa-policy]')].map((r) => r.getAttribute('data-sa-policy'));
    expect(rows).toEqual([
      'builtin.idp',
      'builtin.engine',
      'builtin.job',
      'module.acme.people',
      'builtin.module_bootstrap',
      'builtin.api',
    ]);
    expect(document.querySelector('[data-service-account-policies]')?.textContent).toContain('read-only');
    await mounted.click(document.querySelector('[data-sa-policy="builtin.api"] td'));
    expect(document.querySelector('[data-sa-policy-document="builtin.api"] pre')?.textContent).toContain('triple_store:Query');
    expect(document.querySelector('[data-service-account-policies] button, [data-service-account-policies] textarea')).toBeNull();
  });

  it('shows nothing to whoever may not list the policies', async () => {
    const listPolicies = vi.fn();
    mounted = await mount(ServiceAccountPolicies, { api: fakeApi({ listPolicies }), can: () => false });
    await mounted.flush();
    expect(listPolicies).not.toHaveBeenCalled();
    expect(document.querySelector('[data-service-account-policies]')).toBeNull();
  });
});
