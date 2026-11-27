// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const NAV = vi.hoisted(() => ({ pushed: [] as string[] }));
const CREATE = vi.hoisted(() => vi.fn(async (_ws: string, _input: Record<string, unknown>) => ({ id: 'skill-new' })));

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: (to: string) => NAV.pushed.push(to) }),
  usePathname: () => '/workspace/ws-1/settings/skills/new',
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('@/stores/skills', () => ({ useSkillsStore: () => ({ createSkill: CREATE }) }));

import NewSkillPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  NAV.pushed = [];
});

describe('Workspace settings › Skills › Create skill', () => {
  it('is a page: Create faded until named and prompted, then the skill’s page', async () => {
    mounted = await mount(NewSkillPage, {});
    const create = () => mounted!.host.querySelector('[data-action="create"]') as HTMLButtonElement;
    expect(mounted.host.querySelector('[data-instance-name]')?.textContent).toBe('New skill');
    expect(create().disabled).toBe(true);
    await mounted.type(mounted.host.querySelector('input[aria-label="Name"]'), 'Weekly report');
    expect(create().disabled).toBe(true);
    await mounted.type(mounted.host.querySelector('textarea[aria-label="Prompt"]'), 'Write it');
    expect(create().disabled).toBe(false);
    await mounted.click(create());
    await mounted.flush();
    expect(CREATE).toHaveBeenCalledWith('ws-1', expect.objectContaining({ name: 'Weekly report', prompt: 'Write it', scope: 'user' }));
    expect(NAV.pushed).toEqual(['/workspace/ws-1/settings/skills/skill-new']);
  });
});
