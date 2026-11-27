// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const SERVERS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      id: `server-${n}`,
      name: `Server ${n}`,
      type: 'ollama',
      endpoint: `http://host-${n}:11434`,
      description: i === 36 ? 'Runs next to the zebra pen' : '',
      // The last four are disabled: "Enabled" keeps 41.
      enabled: i < 41,
      status: 'online',
      lastChecked: null,
      createdAt: new Date(0),
      updatedAt: new Date(0),
    };
  }),
);

vi.mock('@/stores/servers', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/servers')>()),
  useServersStore: () => ({
    servers: SERVERS,
    loading: false,
    fetchServers: async () => undefined,
    addServer: async () => undefined,
    updateServer: async () => undefined,
    deleteServer: async () => undefined,
    toggleServer: () => undefined,
    checkServerHealth: async () => undefined,
    checkAllServers: async () => undefined,
    setCurrentWorkspace: () => undefined,
  }),
}));

import { ServersPanel } from './servers-panel';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Settings › Servers', () => {
  it('shows 20 servers a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(ServersPanel, { workspaceId: 'ws-1' });
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-server',
      total: 45,
      search: 'input[placeholder="Search servers by name, endpoint or description..."]',
      far: { id: 'server-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Enabled"]', value: 'enabled' },
    });
  });
});
