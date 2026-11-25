// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const MODELS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    // The last four come from another provider: "Provider one" keeps 41.
    const provider_id = i < 41 ? 'one' : 'two';
    return {
      canonical_id: `model-${n}`,
      model_id: i === 36 ? 'zebra-large' : `model-${n}`,
      provider: provider_id,
      provider_id,
      module_path: 'acme.ai',
      configured: true,
      name: `Model ${n}`,
      description: null,
      image: null,
      context_window: null,
    };
  }),
);
const PROVIDERS = vi.hoisted(() =>
  ['one', 'two'].map((id) => ({
    id,
    name: `Provider ${id}`,
    module_path: 'acme.ai',
    configured: true,
    logo_url: null,
    config_keys: [],
    models: [],
  })),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/workspace/ws-1/settings/models',
}));
vi.mock('@/stores/models', () => ({
  readAvailableProviders: async () => new Response(JSON.stringify(PROVIDERS), { status: 200 }),
  readProviderModels: async () => new Response(JSON.stringify(MODELS), { status: 200 }),
}));

import { ModelsPanel } from './models-panel';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Settings › Models', () => {
  it('shows 20 models a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(ModelsPanel, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-model',
      total: 45,
      search: 'input[placeholder="Search by model, provider, or canonical id..."]',
      far: { id: 'model-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Provider"]', value: 'one' },
    });
  });
});
