// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { clearPageState } from '@/lib/page-state';
import { clearViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
import ProfilePage from './profile';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

const ada: User = {
  id: 'ada',
  email: 'ada@example.invalid',
  name: 'Ada',
  bio: 'Engines',
  job_title: 'Analyst',
  createdAt: new Date(),
};

let mounted: Mounted | null = null;
let patches: Record<string, string>[] = [];

beforeEach(() => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  useAuthStore.setState({ user: ada, csrfToken: 'csrf-ada', isAuthenticated: true });
  clearPageState();
  patches = [];
  vi.stubGlobal('fetch', vi.fn(async (input: string, init: RequestInit = {}) => {
    const path = new URL(input).pathname;
    if (path === '/api/auth/me' && init.method === 'PATCH') {
      const body = JSON.parse(String(init.body)) as Record<string, string>;
      patches.push(body);
      return Response.json({ ...ada, ...body });
    }
    return Response.json({});
  }));
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  vi.unstubAllGlobals();
});

const field = (label: string) => {
  const labels = [...mounted!.host.querySelectorAll('label')];
  const at = labels.find((l) => l.textContent === label)!;
  return at.closest('.account-profile-field')!.querySelector<HTMLInputElement | HTMLTextAreaElement>(
    label === 'Bio' ? 'textarea' : 'input'
  )!;
};

describe('Account › Profile keeps unsaved edits', () => {
  it('fades Save Changes until something changes, as Organization › General', async () => {
    mounted = await mount(ProfilePage, {});
    const save = () =>
      [...mounted!.host.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.includes('Save Changes'))!;
    expect(save().disabled).toBe(true);
    await mounted.type(field('Bio'), 'Analytical engines');
    expect(save().disabled).toBe(false);
  });

  it('a return to the page finds them, without a save', async () => {
    mounted = await mount(ProfilePage, {});
    await mounted.type(field('Bio'), 'Analytical engines');
    await mounted.unmount();

    mounted = await mount(ProfilePage, {});
    expect(field('Bio').value).toBe('Analytical engines');
    expect(mounted.host.textContent).toContain('Unsaved changes.');
  });

  it('a refresh of the user updates the fields not edited and keeps the edited one, as a conflict', async () => {
    mounted = await mount(ProfilePage, {});
    await mounted.type(field('Bio'), 'Analytical engines');
    // The session is read again in the background: the profile changed elsewhere.
    await act(async () => useAuthStore.getState().setUser({ ...ada, bio: 'Notes on engines', job_title: 'Mathematician' }));

    expect(field('Bio').value).toBe('Analytical engines');
    expect(field('Job title').value).toBe('Mathematician');
    expect(mounted.host.textContent).toContain('Changed elsewhere since you began editing: Bio');

    // Save sends the user's version, then nothing is left to keep.
    const save = [...mounted.host.querySelectorAll('button')].find((b) => b.textContent?.includes('Save Changes'))!;
    await mounted.click(save);
    for (let i = 0; i < 20 && patches.length === 0; i += 1) await mounted.flush();
    await mounted.flush();
    expect(patches[0]).toMatchObject({ bio: 'Analytical engines', job_title: 'Mathematician' });
    expect(mounted.host.textContent).not.toContain('Unsaved changes.');
    expect(mounted.host.textContent).not.toContain('Changed elsewhere');
  });

  it('another account never finds them', async () => {
    mounted = await mount(ProfilePage, {});
    await mounted.type(field('Bio'), 'Analytical engines');
    await mounted.unmount();

    await act(async () => useAuthStore.setState({ user: { ...ada, id: 'grace', name: 'Grace', bio: '' } }));
    mounted = await mount(ProfilePage, {});
    expect(field('Bio').value).toBe('');
    expect(field('Full Name').value).toBe('Grace');
  });
});
