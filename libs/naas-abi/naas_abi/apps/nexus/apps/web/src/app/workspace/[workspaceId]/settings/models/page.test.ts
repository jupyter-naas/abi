// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const READ = vi.hoisted(() => vi.fn());
const NAV = vi.hoisted(() => ({ policy: null as string | null }));

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  usePathname: () => '/workspace/ws-1/settings/models',
  useSearchParams: () => ({ get: (key: string) => (key === 'policy' ? NAV.policy : null) }),
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
      createElement('a', { href, ...rest }, children as never),
  };
});
vi.mock('@/lib/access-model/workspace-offer', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/access-model/workspace-offer')>()),
  createOfferApi: () => ({ read: READ }),
}));
// The offer's Models part is the offer editor's: checked on its own.
vi.mock('@/components/access/offer/offer-editor', () => ({ WorkspaceOfferEditor: () => null }));
vi.mock('@/components/settings/models-panel', () => ({ ModelsPanel: () => 'PLATFORM CATALOG' }));

import ModelsPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  READ.mockReset();
});

describe('Workspace settings › Models', () => {
  it("keeps the workspace's part only, with one total, and links to the platform's catalog", async () => {
    READ.mockResolvedValue({ models: { offered: ['gpt-a', 'gpt-b'], default: 'gpt-a', every: false, available: [] } });
    mounted = await mount(ModelsPage, {});
    await mounted.flush();
    expect(mounted.host.querySelector('h2')?.textContent).toBe('Models');
    expect(mounted.host.textContent).toContain('2 models');
    expect(mounted.host.textContent).not.toContain('PLATFORM CATALOG');
    // The catalog the models are picked from, in the workspace (each model opens its page).
    expect(mounted.host.querySelector('a[data-action="model-catalog"]')?.getAttribute('href')).toBe('/workspace/ws-1/settings/models/catalog');
  });

  it('reads the policy picked in the Settings column', async () => {
    NAV.policy = 'pol_g';
    READ.mockResolvedValue({ models: { offered: ['gpt-a'], default: 'gpt-a', every: false, available: [] } });
    mounted = await mount(ModelsPage, {});
    await mounted.flush();
    NAV.policy = null;
    expect(READ).toHaveBeenCalledWith('ws-1', 'pol_g');
    expect(mounted.host.textContent).toContain('1 model');
    expect(mounted.host.textContent).toContain('Granted by the policy picked');
  });

  it('says Every model when the workspace uses them all', async () => {
    READ.mockResolvedValue({ models: { offered: ['*'], default: null, every: true, available: [] } });
    mounted = await mount(ModelsPage, {});
    await mounted.flush();
    expect(mounted.host.textContent).toContain('Every model');
  });
});
