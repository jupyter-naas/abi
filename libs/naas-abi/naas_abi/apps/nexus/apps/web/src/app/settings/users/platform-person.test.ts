// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const PERSON = 'usr_01m7n7jm9qwmqc0tmaqswbpprw';
const principal = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock('next/navigation', () => ({
  usePathname: () => `/settings/users/${PERSON}`,
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock('@/lib/iam-admin/api', () => ({
  createIamAdminApi: () => ({ getPrincipal: vi.fn(async () => principal.value) }),
}));
vi.mock('@/components/access/people/view-as-control', () => ({ ViewAsControl: () => null }));
vi.mock('@/components/people/member-role-section', () => ({ MemberRoleSection: () => null }));
// Their organizations: the account's answer, given to the page as the real section does.
const account = vi.hoisted(() => ({
  value: null as null | { name?: string | null; email?: string | null; avatar?: string | null },
}));
vi.mock('./platform-organizations', async () => {
  const { useEffect } = await import('react');
  return {
    PlatformOrganizations: ({ onAccess }: { onAccess?: (a: unknown) => void }) => {
      useEffect(() => {
        onAccess?.(account.value ? { user_id: 'u', principal_id: PERSON, ...account.value } : null);
        // Once, as the real section answers once per person.
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
      return null;
    },
  };
});

import PlatformPersonPage from './platform-person';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Platform › Users › a person', () => {
  it('is named from their account when their IAM principal has no name or email', async () => {
    principal.value = { id: PERSON, display_name: null, email: null, name: null };
    account.value = { name: 'Aaron Clayton', email: 'aaron@example.invalid' };
    mounted = await mount(PlatformPersonPage, {});
    await mounted.flush();
    await mounted.flush();
    expect(mounted.host.textContent).toContain('Aaron Clayton');
    expect(mounted.host.textContent).toContain('aaron@example.invalid');
    expect(mounted.host.querySelector('h1, h2')?.textContent ?? '').not.toContain(PERSON);
  });

  it('keeps the name IAM gives, and falls back on the id only when neither knows one', async () => {
    principal.value = { id: PERSON, display_name: 'Dana Scully', email: 'dana@example.invalid' };
    account.value = { name: 'Other', email: 'other@example.invalid' };
    mounted = await mount(PlatformPersonPage, {});
    await mounted.flush();
    await mounted.flush();
    expect(mounted.host.textContent).toContain('Dana Scully');
    expect(mounted.host.textContent).not.toContain('Other');
    await mounted.unmount();

    principal.value = { id: PERSON };
    account.value = null;
    mounted = await mount(PlatformPersonPage, {});
    await mounted.flush();
    await mounted.flush();
    expect(mounted.host.textContent).toContain(PERSON);
  });
});
