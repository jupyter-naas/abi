// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const STORE = vi.hoisted(() => {
  const skill = {
    id: 'skill-1',
    workspaceId: 'ws-1',
    organizationId: null,
    userId: 'user-1',
    name: 'Weekly report',
    slug: 'weekly-report',
    description: 'Writes the weekly report',
    prompt: 'Write it',
    scope: 'workspace',
    enabled: true,
    lastUsedAt: null,
    createdAt: '2026-11-01T00:00:00Z',
    updatedAt: '2026-11-01T00:00:00Z',
  };
  return {
    skillsByWorkspace: { 'ws-1': [skill] },
    fetchSkills: async () => undefined,
    updateSkill: vi.fn(async (_id: string, updates: Record<string, unknown>) => ({ ...skill, ...updates })),
  };
});

vi.mock('next/navigation', () => ({
  // No policy picked: "<W> access" (`usePolicyHref` reads the URL).
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ workspaceId: 'ws-1', skillId: 'skill-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/workspace/ws-1/settings/skills/skill-1',
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('@/stores/skills', () => ({ useSkillsStore: () => STORE }));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (state: unknown) => unknown) => select({ user: { id: 'user-1' } }),
}));

import SkillEditorPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Skills › a skill', () => {
  it('has the person-page header, Save faded until something changes, the unsaved bar', async () => {
    mounted = await mount(SkillEditorPage, {});
    await mounted.flush();
    const m = mounted;
    const save = () => m.host.querySelector('[data-action="save"]') as HTMLButtonElement;
    expect(m.host.querySelector('[data-instance-name]')?.textContent).toBe('Weekly report');
    expect(m.host.querySelector('[data-instance-ids]')?.textContent).toBe('/weekly-report · skill-1');
    expect(save().disabled).toBe(true);
    await m.type(m.host.querySelector('textarea[aria-label="Prompt"]'), 'Write it well');
    expect(save().disabled).toBe(false);
    expect(m.host.querySelector('[data-unsaved-bar]')).not.toBeNull();
    await m.click(save());
    await m.flush();
    expect(STORE.updateSkill).toHaveBeenCalledWith('skill-1', expect.objectContaining({ prompt: 'Write it well' }));
  });
});
