// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const SKILLS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      id: `skill-${n}`,
      workspaceId: 'ws-1',
      organizationId: null,
      userId: 'user-1',
      name: `Skill ${n}`,
      slug: `skill-${n}`,
      description: i === 36 ? 'Writes about the zebra herd' : `The skill number ${n}`,
      prompt: 'Do it',
      scope: 'workspace',
      // The last four are disabled: "Enabled" keeps 41.
      enabled: i < 41,
      lastUsedAt: null,
      createdAt: '2026-11-01T00:00:00Z',
      updatedAt: '2026-11-01T00:00:00Z',
    };
  }),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/workspace/ws-1/settings/skills',
}));
vi.mock('@/stores/skills', () => ({
  useSkillsStore: () => ({
    skillsByWorkspace: { 'ws-1': SKILLS },
    fetchSkills: async () => undefined,
    createSkill: async () => undefined,
    updateSkill: async () => undefined,
    deleteSkill: async () => undefined,
  }),
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (state: unknown) => unknown) => select({ user: { id: 'user-1' } }),
}));

import SkillsSettingsPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Skills', () => {
  it('shows 20 skills a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(SkillsSettingsPage, {});
    await checkPagedTable(mounted, {
      row: 'data-skill',
      total: 45,
      search: 'input[placeholder="Search skills..."]',
      far: { id: 'skill-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Status"]', value: 'enabled' },
    });
  });
});
