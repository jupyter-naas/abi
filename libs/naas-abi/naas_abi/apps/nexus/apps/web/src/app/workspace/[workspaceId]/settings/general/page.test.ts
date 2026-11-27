// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));
// The config preseeding and the group list read the API: not under test here.
// The wallpaper editor stands in: its props are kept, and the page's Save and Discard reach it.
const wallpaper = vi.hoisted(() => ({
  props: null as null | { control?: { current: unknown }; onDirtyChange?: (dirty: boolean) => void },
  save: null as unknown as ReturnType<typeof import('vitest').vi.fn>,
  discard: null as unknown as ReturnType<typeof import('vitest').vi.fn>,
}));
vi.mock('../../home/components/background-image-editor', () => ({
  BackgroundImageEditor: (props: typeof wallpaper.props) => {
    wallpaper.props = props;
    if (props?.control) props.control.current = { save: wallpaper.save, discard: wallpaper.discard };
    return null;
  },
}));
vi.mock('./workspace-configuration', () => ({ WorkspaceConfiguration: () => null }));
vi.mock('@/lib/home-background', () => ({ fetchCurrentBackgroundImage: vi.fn(async () => undefined) }));
vi.mock('@/lib/workspace-groups', () => ({ existingWorkspaceGroups: vi.fn(async () => ['Audit']) }));

import { clearPageState } from '@/lib/page-state';
import { clearResources } from '@/lib/resource-cache';
import { clearViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
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

const admin: User = { id: 'admin', email: 'admin@example.invalid', name: 'Admin', createdAt: new Date() };

beforeEach(() => {
  // Page drafts belong to a signed-in session (lib/page-state.ts), as Organization › General's.
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  useAuthStore.setState({ user: admin, csrfToken: 'csrf-admin', isAuthenticated: true });
  clearPageState();
  clearResources();
  useWorkspaceStore.setState({ workspaces: [WORKSPACE], currentWorkspaceId: 'ws-1' });
  wallpaper.save = vi.fn(async () => true);
  wallpaper.discard = vi.fn();
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
    // Save changes is Organization › General's button: disabled (faded) until something changes.
    const save = m.host.querySelector<HTMLButtonElement>('button.org-settings-primary-button')!;
    expect(save.disabled).toBe(true);

    const name = m.host.querySelector<HTMLInputElement>('#workspace-name')!;
    await m.type(name, 'Alpha Prime');
    const draft = m.host.querySelector('.org-settings-general-draft[role="status"]');
    expect(draft?.querySelector('.org-settings-general-draft-text')?.textContent).toBe('Unsaved changes.');
    expect(save.disabled).toBe(false);

    await m.click(draft!.querySelector('button.org-settings-general-draft-discard'));
    expect(m.host.querySelector<HTMLInputElement>('#workspace-name')!.value).toBe('Alpha');
    expect(m.host.querySelector('.org-settings-general-draft')).toBeNull();
  });
});

describe('Workspace › General saves the wallpaper with the page', () => {
  it('shows no wallpaper buttons of its own: the page Save commits it, Discard drops it', async () => {
    const m = await open();
    const { act } = await import('react');
    await act(async () => wallpaper.props?.onDirtyChange?.(true));
    expect(m.host.querySelector('.org-settings-general-draft')?.textContent).toContain('Unsaved changes.');
    const save = [...m.host.querySelectorAll('button')].find((b) => b.textContent?.includes('Save changes'))!;
    expect(save.disabled).toBe(false);
    await m.click(save);
    await m.flush();
    expect(wallpaper.save).toHaveBeenCalledTimes(1);

    await m.click(m.host.querySelector('button.org-settings-general-draft-discard'));
    expect(wallpaper.discard).toHaveBeenCalledTimes(1);
  });
});

describe('Workspace › General keeps unsaved edits, as Organization › General', () => {
  it('a return finds them, and the wallpaper editor is told where to keep its own', async () => {
    let m = await open();
    await m.type(m.host.querySelector('#workspace-name'), 'Alpha Prime');
    await m.unmount();
    mounted = null;

    m = await open();
    expect(m.host.querySelector<HTMLInputElement>('#workspace-name')!.value).toBe('Alpha Prime');
    expect(m.host.querySelector('.org-settings-general-draft')?.textContent).toContain('Unsaved changes.');
    expect((wallpaper.props as { keepAs?: unknown } | null)?.keepAs).toEqual({
      scope: 'workspace:ws-1',
      page: 'general',
      detail: 'wallpaper',
    });
  });
});
