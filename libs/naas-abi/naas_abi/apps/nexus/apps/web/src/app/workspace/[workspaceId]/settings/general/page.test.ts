// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
// The wallpaper, the config preseeding and the group list read the API: not under test here.
vi.mock('../../home/components/background-image-editor', () => ({ BackgroundImageEditor: () => null }));
vi.mock('./workspace-configuration', () => ({ WorkspaceConfiguration: () => null }));
vi.mock('@/lib/home-background', () => ({ fetchCurrentBackgroundImage: vi.fn(async () => undefined) }));
vi.mock('@/lib/workspace-groups', () => ({ existingWorkspaceGroups: vi.fn(async () => ['Audit']) }));

import { DEFAULT_THEME, useWorkspaceStore, type Workspace } from '@/stores/workspace';
import GeneralSettingsPage from './page';

const WORKSPACE = {
  id: 'ws-1',
  name: 'Alpha',
  slug: 'alpha',
  description: 'The first one',
  group: 'Audit',
  theme: DEFAULT_THEME,
  branches: [],
  currentBranchId: 'main',
  createdAt: new Date(),
  updatedAt: new Date(),
  currentUserRole: 'admin',
} as Workspace;

let mounted: Mounted | null = null;

beforeEach(() => {
  useWorkspaceStore.setState({ workspaces: [WORKSPACE], currentWorkspaceId: 'ws-1' });
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function open() {
  mounted = await mount(GeneralSettingsPage, {});
  await mounted.flush();
  return mounted;
}

const label = (m: Mounted, id: string) => m.host.querySelector(`label[for="${id}"]`)?.textContent;

describe('Workspace › General', () => {
  it('lays out Name and Slug side by side, then Workspace Group', async () => {
    const m = await open();
    const fields = [...m.host.querySelectorAll('.account-profile-form-grid > .account-profile-field label')].map(
      (l) => l.textContent
    );
    expect(fields).toEqual(['Name', 'Slug', 'Workspace Group']);
    expect(label(m, 'workspace-name')).toBe('Name');
    expect(label(m, 'workspace-group')).toBe('Workspace Group');
  });

  it('says there are unsaved changes, as Organization › General, and discards them', async () => {
    const m = await open();
    expect(m.host.querySelector('.org-settings-general-draft')).toBeNull();

    const name = m.host.querySelector<HTMLInputElement>('#workspace-name')!;
    await m.type(name, 'Alpha Prime');
    const draft = m.host.querySelector('.org-settings-general-draft[role="status"]');
    expect(draft?.querySelector('.org-settings-general-draft-text')?.textContent).toBe('Unsaved changes.');

    await m.click(draft!.querySelector('button.org-settings-general-draft-discard'));
    expect(m.host.querySelector<HTMLInputElement>('#workspace-name')!.value).toBe('Alpha');
    expect(m.host.querySelector('.org-settings-general-draft')).toBeNull();
  });
});
