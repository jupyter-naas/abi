// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const MODELS = vi.hoisted(() =>
  Array.from({ length: 46 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    // The last five come from another provider: "Provider one" keeps 41. The last one is not
    // configured: the table hides it at first.
    const provider_id = i < 41 ? 'one' : 'two';
    return {
      canonical_id: `model-${n}`,
      model_id: i === 36 ? 'zebra-large' : `model-${n}`,
      provider: provider_id,
      provider_id,
      module_path: 'acme.ai',
      configured: i < 45,
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
const push = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({
  // No policy picked: "<W> access" (`usePolicyHref` reads the URL).
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push }),
  usePathname: () => '/workspace/ws-1/settings/models',
}));
vi.mock('@/stores/models', () => ({
  readAvailableProviders: async () => new Response(JSON.stringify(PROVIDERS), { status: 200 }),
  readProviderModels: async () => new Response(JSON.stringify(MODELS), { status: 200 }),
}));

import { ModelsPanel } from './models-panel';
import { pickColumnFilter as pickFacet } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  window.localStorage.clear();
});

async function render() {
  const m = (mounted = await mount(ModelsPanel, {}));
  await m.flush();
  return m;
}

describe('Settings › Models', () => {
  it('shows 20 models a page, searches and filters all of them from the columns, back to the first page', async () => {
    const m = await render();
    const q = (selector: string) => m.host.querySelector(selector);
    const rows = () => [...m.host.querySelectorAll('[data-model]')].map((r) => r.getAttribute('data-model'));
    const shown = () => q('[data-field="rows-shown"]')?.textContent;

    expect(q('select[aria-label="Provider"]')).toBeNull();
    expect(q('select[aria-label="Status"]')).toBeNull();
    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    await m.select(q('[data-field="page-size"]'), '50');
    expect(rows()).toHaveLength(45);
    await m.select(q('[data-field="page-size"]'), '20');

    // The search reaches every row, not only the page shown.
    await m.type(q('input[placeholder="Search by model, provider, or canonical id..."]'), 'zebra');
    expect(rows()).toEqual(['model-37']);
    await m.type(q('input[placeholder="Search by model, provider, or canonical id..."]'), '');

    // The Provider column filters, and goes back to the first page.
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await pickFacet(m, 'provider', 'Provider one');
    expect(shown()).toBe('Rows 1–20 of 41');
  });

  it('shows the configured models at first, from the Status column; Clear shows them all', async () => {
    const m = await render();
    const q = (selector: string) => m.host.querySelector(selector);

    expect(m.host.textContent).toContain('45 of 46 models');
    expect(q('[data-filter-trigger="status"]')?.classList.contains('is-active')).toBe(true);
    expect(q('[data-model="model-46"]')).toBeNull();

    await m.click(q('[data-action="clear-filters"]'));
    expect(m.host.textContent).toContain('46 models');
    await m.click(q('[data-sort="status"]'));
    await m.click(q('[data-sort="status"]'));
    expect(q('[data-model]')?.getAttribute('data-model')).toBe('model-46');
  });

  it('opens a model from its row and draws only the columns chosen', async () => {
    const m = await render();

    await m.click(m.host.querySelector('[data-model="model-01"] td'));
    expect(push).toHaveBeenCalledWith('/workspace/ws-1/settings/models/model-01');
    expect(
      [...m.host.querySelectorAll('thead th')].map((th) => th.textContent),
    ).toEqual(['Image', 'Name', 'Model ID', 'Provider', 'Description', 'Context', 'Status']);
    expect(m.host.querySelector('[data-filter-trigger="image"]')).toBeNull();
  });
});
