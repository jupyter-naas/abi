// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const SERVICES = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => ({
    id: i === 36 ? 'zebra_store' : `service_${String(i + 1).padStart(2, '0')}`,
    // The last four run on s3: the "fs" provider keeps 41.
    adapters: [i < 41 ? 'fs' : 's3'],
  })),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ orgId: 'org-1' }),
  useRouter: () => ({ push: () => undefined }),
  usePathname: () => '/organizations/org-1/settings/services',
}));
vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children }: { href: string; children: unknown }) => createElement('a', { href }, children as never),
  };
});
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  authFetch: async () => new Response(JSON.stringify(SERVICES), { status: 200 }),
}));

import ServicesSettingsPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Organization settings › Services', () => {
  it('shows 20 services a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(ServicesSettingsPage, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-service',
      total: 45,
      search: 'input[placeholder="Search services..."]',
      far: { id: 'zebra_store', query: 'zebra' },
      filter: { select: 'select[aria-label="Provider"]', value: 'fs' },
    });
  });
});
