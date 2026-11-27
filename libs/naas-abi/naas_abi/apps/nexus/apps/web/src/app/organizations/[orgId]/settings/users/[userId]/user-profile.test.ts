// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
vi.mock('next/navigation', () => ({
  useParams: () => ({ orgId: 'acme', userId: 'u-aaron' }),
  useRouter: () => ({ push: vi.fn() }),
}));
// What they hold and View as read IAM: not under test here.
vi.mock('@/components/people/member-role-section', () => ({ MemberRoleSection: () => null }));
vi.mock('@/components/access/people/view-as-control', () => ({ ViewAsControl: () => null }));
const authFetch = vi.hoisted(() => vi.fn());
vi.mock('@/stores/auth', async (original) => ({ ...(await original<object>()), authFetch }));

import { clearPageState } from '@/lib/page-state';
import { clearViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
import OrgUserProfilePage from './user-profile';

const admin: User = { id: 'admin', email: 'admin@example.invalid', name: 'Admin', createdAt: new Date() };
const DETAILS = {
  member: {
    id: 'm1',
    organization_id: 'acme',
    user_id: 'u-aaron',
    principal_id: 'usr_aaron',
    role: null,
    email: 'aaron@example.invalid',
    name: 'Aaron Clayton',
    created_at: null,
  },
  account: { user_id: 'u-aaron', email: 'aaron@example.invalid', name: 'Aaron Clayton', avatar: null, organization: null, job_title: null, bio: null },
  organization_profile: { organization: 'Acme UK', job_title: '', service_line: '', country: '', interest: '', bio: '', avatar: null },
  workspaces: [],
};

let mounted: Mounted | null = null;

beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: admin, csrfToken: 'csrf-admin', isAuthenticated: true });
  clearPageState();
  authFetch.mockReset();
  authFetch.mockImplementation(async () => Response.json(DETAILS));
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function open() {
  mounted = await mount(OrgUserProfilePage, {});
  for (let i = 0; i < 10 && !mounted.host.querySelector('[data-instance-header]'); i += 1) await mounted.flush();
  return mounted;
}

describe('Organization › Users › a person', () => {
  it('changes their picture in the header, as Account › Profile, with no Reload', async () => {
    const m = await open();
    const header = m.host.querySelector('[data-instance-header]')!;
    expect(header.querySelector('[data-member-avatar] [data-action="upload-picture"]')).not.toBeNull();
    expect(header.querySelector('[data-instance-name]')?.textContent).toBe('Aaron Clayton');
    expect(header.textContent).toContain('aaron@example.invalid');
    expect(header.querySelector('[data-action="reload"]')).toBeNull();
    expect(header.querySelector('[data-action="remove-member"]')).not.toBeNull();
  });

  it('shows Info and Profile as one untitled section, name and email once', async () => {
    const m = await open();
    expect(m.host.querySelector('details')).toBeNull();
    expect([...m.host.querySelectorAll('section h3')].map((h) => h.textContent)).toEqual([]);
    const labels = [...m.host.querySelectorAll('[data-section="profile"] label')].map((l) => l.textContent);
    expect(labels.filter((l) => l === 'Name')).toHaveLength(1);
    expect(labels.filter((l) => l === 'Email')).toHaveLength(1);
    expect(labels).not.toContain('Full name');
  });

  it('fades Save changes until something changes, then shows the unsaved bar', async () => {
    const m = await open();
    const save = m.host.querySelector<HTMLButtonElement>('[data-action="save-profile"]')!;
    expect(save.disabled).toBe(true);
    await m.type(m.host.querySelector('#org-member-job_title'), 'Partner');
    expect(save.disabled).toBe(false);
    expect(m.host.querySelector('.org-settings-general-draft')?.textContent).toContain('Unsaved changes.');
  });
});
