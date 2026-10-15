import { appsPath } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';
import { filesBrowsePath } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import type { StarredItem } from '@/stores/files';
import type { DeskSurfaceId } from './home-desk';

const SURFACE_LABELS: Record<DeskSurfaceId, string> = {
  chat: 'Chat',
  files: 'Files',
};

export type HomeFileMenuRow =
  | {
      kind: 'item';
      id: string;
      label: string;
      href: string;
      navigate: () => void;
    }
  | { kind: 'separator'; id: string };

type DesktopApp = {
  app_id: string;
  name: string;
  enabled?: boolean;
  installed?: boolean;
  url?: string | null;
};

function pushSeparatorBefore(rows: HomeFileMenuRow[], id: string) {
  if (rows.length > 0 && rows[rows.length - 1]?.kind !== 'separator') {
    rows.push({ kind: 'separator', id });
  }
}

/** File menu rows mirror the icons on the home desk (same labels and destinations). */
export function buildHomeFileMenuRows(params: {
  workspaceId: string;
  isMobile: boolean;
  surfaces: DeskSurfaceId[];
  apps: DesktopApp[];
  starredItems: StarredItem[];
  onOpenSurface: (section: DeskSurfaceId) => void;
  onOpenApp: (appId: string) => void;
  onOpenStarred: (item: StarredItem) => void;
}): HomeFileMenuRow[] {
  const {
    workspaceId,
    isMobile,
    surfaces,
    apps,
    starredItems,
    onOpenSurface,
    onOpenApp,
    onOpenStarred,
  } = params;

  const rows: HomeFileMenuRow[] = [];

  for (const section of surfaces) {
    rows.push({
      kind: 'item',
      id: `surface-${section}`,
      label: SURFACE_LABELS[section],
      href: getWorkspacePath(workspaceId, `/${section}`),
      navigate: () => onOpenSurface(section),
    });
  }

  const desktopApps = apps.filter((a) => a.enabled && a.installed && a.url);
  if (desktopApps.length > 0) pushSeparatorBefore(rows, 'sep-apps');
  for (const app of desktopApps) {
    rows.push({
      kind: 'item',
      id: `app-${app.app_id}`,
      label: app.name,
      href: appsPath(workspaceId, app.app_id),
      navigate: () => onOpenApp(app.app_id),
    });
  }

  const deskStarred = starredItems.filter((item) => item.workspaceId === workspaceId);
  const filesHref = isMobile
    ? filesBrowsePath(workspaceId)
    : getWorkspacePath(workspaceId, '/files');

  if (deskStarred.length > 0) pushSeparatorBefore(rows, 'sep-starred');
  for (const item of deskStarred) {
    rows.push({
      kind: 'item',
      id: `starred-${item.source}:${item.path}`,
      label: item.name,
      href: filesHref,
      navigate: () => onOpenStarred(item),
    });
  }

  return rows;
}
