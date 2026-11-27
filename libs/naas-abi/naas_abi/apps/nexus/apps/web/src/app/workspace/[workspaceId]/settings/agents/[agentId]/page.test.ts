// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const UPDATE = vi.hoisted(() => vi.fn(async () => undefined));
// Stable as the stores' own are: the page reads again when they change.
const STORES = vi.hoisted(() => ({
  agents: { agents: [{ id: 'agent-1', tools: [] }] as unknown[], updateAgent: undefined as unknown },
  integrations: { refreshProviders: async () => undefined },
}));
const ROSTER = vi.hoisted(() => [
  {
    id: 'agent-1',
    workspace_id: 'ws-1',
    name: 'Coach',
    description: 'Coaches people',
    class_name: 'acme.people/Coach',
    system_prompt: 'Be kind.',
    model_id: 'gpt-test',
    provider: 'openai',
    logo_url: null,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
  },
]);

vi.mock('next/navigation', () => ({
  // No policy picked: "<W> access" (`usePolicyHref` reads the URL).
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ workspaceId: 'ws-1', agentId: 'agent-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/workspace/ws-1/settings/agents/agent-1',
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('@/stores/agents', () => ({
  readAgentRoster: async () => ROSTER,
  useAgentsStore: () => ({ ...STORES.agents, updateAgent: UPDATE }),
}));
vi.mock('@/stores/integrations', () => ({ useIntegrationsStore: () => STORES.integrations }));

import AgentEditPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Agents › an agent', () => {
  it('has the person-page header, Save faded until something changes, the unsaved bar, Discard', async () => {
    mounted = await mount(AgentEditPage, {});
    await mounted.flush();
    const m = mounted;
    const save = () => m.host.querySelector('[data-action="save"]') as HTMLButtonElement;
    const name = () => m.host.querySelector('input[aria-label="Name"]') as HTMLInputElement;
    expect(m.host.querySelector('[data-instance-name]')?.textContent).toBe('Coach');
    expect(m.host.querySelector('[data-instance-ids]')?.textContent).toBe('agent-1');
    expect(m.host.querySelector('[data-instance-meta] a[data-module-link]')?.textContent).toBe('acme.people');
    expect(save().disabled).toBe(true);
    expect(m.host.querySelector('[data-unsaved-bar]')).toBeNull();

    await m.type(name(), 'Coach 2');
    expect(save().disabled).toBe(false);
    expect(m.host.querySelector('[data-unsaved-bar]')?.textContent).toContain('Unsaved changes.');
    await m.click(m.host.querySelector('[data-unsaved-bar] [data-action="discard"]'));
    expect(name().value).toBe('Coach');
    expect(save().disabled).toBe(true);

    await m.type(name(), 'Coach 2');
    await m.click(save());
    await m.flush();
    expect(UPDATE).toHaveBeenCalledWith('agent-1', expect.objectContaining({ name: 'Coach 2', systemPrompt: 'Be kind.' }));
  });
});
