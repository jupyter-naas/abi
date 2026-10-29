import { describe, expect, it, vi } from 'vitest';

import { buildHomeFileMenuRows } from './home-desk-nav';

describe('buildHomeFileMenuRows', () => {
  it('lists surfaces, apps, and starred items with the same hrefs as the desk', () => {
    const onOpenSurface = vi.fn();
    const onOpenApp = vi.fn();
    const onOpenStarred = vi.fn();

    const rows = buildHomeFileMenuRows({
      workspaceId: 'ws-1',
      isMobile: false,
      surfaces: ['chat', 'files'],
      apps: [
        {
          app_id: 'maps',
          name: 'Maps',
          installed: true,
          url: '/maps',
        },
      ],
      starredItems: [
        {
          workspaceId: 'ws-1',
          source: 'my-drive',
          path: 'notes/readme.md',
          name: 'readme.md',
          type: 'file',
        },
      ],
      onOpenSurface,
      onOpenApp,
      onOpenStarred,
    });

    const items = rows.filter((r) => r.kind === 'item');
    expect(items.map((i) => i.label)).toEqual(['Chat', 'Files', 'Maps', 'readme.md']);
    expect(items[0]?.href).toBe('/workspace/ws-1/chat');
    expect(items[1]?.href).toBe('/workspace/ws-1/files');
    expect(items[2]?.href).toBe('/workspace/ws-1/apps?open=maps');
    expect(items[3]?.href).toBe('/workspace/ws-1/files');

    items[0]?.navigate();
    expect(onOpenSurface).toHaveBeenCalledWith('chat');
  });
});
