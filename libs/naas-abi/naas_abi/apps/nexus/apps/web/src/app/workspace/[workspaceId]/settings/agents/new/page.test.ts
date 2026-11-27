// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const NAV = vi.hoisted(() => ({ pushed: [] as string[] }));
const ADD = vi.hoisted(() => vi.fn(async (_agent: Record<string, unknown>) => 'agent-new'));

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: (to: string) => NAV.pushed.push(to) }),
  usePathname: () => '/workspace/ws-1/settings/agents/new',
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('@/stores/agents', () => ({ useAgentsStore: () => ({ addAgent: ADD }) }));

import NewAgentPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  NAV.pushed = [];
});

describe('Workspace settings › Agents › Create agent', () => {
  it('is a page: the instance header, Create faded until named, then the agent’s page', async () => {
    mounted = await mount(NewAgentPage, {});
    const create = () => mounted!.host.querySelector('[data-action="create"]') as HTMLButtonElement;
    expect(mounted.host.querySelector('[data-instance-name]')?.textContent).toBe('New agent');
    expect(create().disabled).toBe(true);
    expect(mounted.host.querySelector('a[data-action="back"]')?.getAttribute('href')).toBe('/workspace/ws-1/settings/agents');

    await mounted.type(mounted.host.querySelector('input[aria-label="Name"]'), 'Coach');
    expect(mounted.host.querySelector('[data-instance-name]')?.textContent).toBe('Coach');
    expect(mounted.host.querySelector('[data-unsaved-bar]')).not.toBeNull();
    expect(create().disabled).toBe(false);
    await mounted.click(create());
    await mounted.flush();
    expect(ADD.mock.calls[0][0]).toMatchObject({ name: 'Coach', systemPrompt: 'You are a helpful AI assistant.' });
    expect(NAV.pushed).toEqual(['/workspace/ws-1/settings/agents/agent-new']);
  });
});
