// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

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
      // The last four are disabled: the Enabled column filtered on Enabled keeps 41.
      enabled: i < 41,
      lastUsedAt: null,
      createdAt: '2026-11-01T00:00:00Z',
      updatedAt: '2026-11-01T00:00:00Z',
    };
  }),
);

const UPDATE = vi.hoisted(() => vi.fn(async (_id: string, _patch: Record<string, unknown>) => undefined));

vi.mock('next/navigation', () => ({
  // No policy picked: "<W> access" (`usePolicyHref` reads the URL).
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/workspace/ws-1/settings/skills',
}));
vi.mock('@/stores/skills', () => ({
  useSkillsStore: () => ({
    skillsByWorkspace: { 'ws-1': SKILLS },
    fetchSkills: async () => undefined,
    createSkill: async () => undefined,
    updateSkill: UPDATE,
    deleteSkill: async () => undefined,
  }),
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  useAuthStore: (select: (state: unknown) => unknown) => select({ user: { id: 'user-1' } }),
}));

import SkillsSettingsPage from './page';
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Skills', () => {
  it('shows 20 skills a page, searches all of them, a column filter goes back to the first page', async () => {
    mounted = await mount(SkillsSettingsPage, {});
    const m = mounted;
    const q = (selector: string) => m.host.querySelector(selector);
    const rows = () => [...m.host.querySelectorAll('[data-skill]')].map((r) => r.getAttribute('data-skill'));
    const shown = () => q('[data-field="rows-shown"]')?.textContent ?? null;

    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    expect(rows()).not.toContain('skill-37');
    await m.select(q('[data-field="page-size"]'), '50');
    expect(rows()).toHaveLength(45);
    await m.select(q('[data-field="page-size"]'), '20');
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toBe('Rows 21–40 of 45');

    // The search reaches every skill, not only the page shown.
    await m.type(q('input[placeholder="Search skills..."]'), 'zebra');
    expect(rows()).toEqual(['skill-37']);
    // One total in the badge, no count above the search.
    expect(m.host.textContent).toContain('45 skills');
    expect(m.host.textContent).not.toContain('1 of 45 skills');

    // The Enabled column filters on the status, and goes back to the first page.
    await m.type(q('input[placeholder="Search skills..."]'), '');
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await filterColumn(m, 'enabled', 'Enabled');
    expect(shown()).toBe('Rows 1–20 of 41');
    expect(m.host.textContent).not.toContain('41 enabled');

    await m.click(q('[data-action="clear-filters"]'));
    expect(shown()).toBe('Rows 1–20 of 45');
  });

  it('filters the disabled skills from the Enabled column, then Visibility and the search narrow them', async () => {
    mounted = await mount(SkillsSettingsPage, {});
    await filterColumn(mounted, 'enabled', 'Disabled');
    expect([...mounted.host.querySelectorAll('[data-skill]')].map((r) => r.getAttribute('data-skill'))).toEqual([
      'skill-42',
      'skill-43',
      'skill-44',
      'skill-45',
    ]);
    await filterColumn(mounted, 'visibility', 'Workspace');
    expect(mounted.host.querySelectorAll('[data-skill]')).toHaveLength(4);
    // The search narrows the filtered rows: the zebra skill is enabled.
    await mounted.type(mounted.host.querySelector('input[placeholder="Search skills..."]'), 'zebra');
    expect(mounted.host.querySelectorAll('[data-skill]')).toHaveLength(0);
    expect(mounted.host.textContent).toContain('No skills match the current search and filters');
    expect(mounted.host.querySelector('[data-action="export"]')).not.toBeNull();
    expect([...mounted.host.querySelectorAll('button')].map((b) => b.textContent)).toContain('Create skill');
  });

  it('enables the skills selected in one step, asked first, and says so', async () => {
    UPDATE.mockClear();
    mounted = await mount(SkillsSettingsPage, {});
    await filterColumn(mounted, 'enabled', 'Disabled');
    await mounted.click(mounted.host.querySelector('[data-select-row="skill-42"]'));
    await mounted.click(mounted.host.querySelector('[data-select-row="skill-43"]'));
    await mounted.click(mounted.host.querySelector('[data-bulk-action="on"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Enable 2 skills?');
    const confirm = [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find(
      (b) => b.textContent === 'Enable',
    )!;
    await mounted.click(confirm);
    await mounted.flush();
    expect(UPDATE.mock.calls).toEqual([
      ['skill-42', { enabled: true }],
      ['skill-43', { enabled: true }],
    ]);
    expect(mounted.host.querySelector('[data-skills-notice]')?.textContent).toBe('2 skills enabled.');
  });
});
