'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { File, Folder, MessageSquare } from 'lucide-react';
import { appsPath } from '@/app/workspace/[workspaceId]/apps/lib/apps-route';
import { filesBrowsePath } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import { Header } from '@/components/shell/header';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { useFeature } from '@/hooks/use-feature';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useAppsStore } from '@/stores/apps';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { deskSurfaceIcons, resolveDeskImageUrl, wallpaperStyle, type DeskSurfaceId } from './home-desk';

export default function HomePage() {
  const router = useRouter();
  const isMobile = useIsMobile();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const setActivePanelSection = useWorkspaceStore((s) => s.setActivePanelSection);
  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const theme = workspace?.theme;
  const canChat = useFeature('chat');
  const canFiles = useFeature('files');

  const fetchApps = useAppsStore((s) => s.fetchApps);
  const apps = useAppsStore((s) => s.apps);
  const starredItems = useFilesStore((s) => s.starredItems);
  const setStarredNavigation = useFilesStore((s) => s.setStarredNavigation);
  const setActiveSource = useFilesStore((s) => s.setActiveSource);

  useEffect(() => {
    if (currentWorkspaceId) void fetchApps(currentWorkspaceId);
  }, [currentWorkspaceId, fetchApps]);

  const surfaceIcons = deskSurfaceIcons({ chat: canChat, files: canFiles });
  const desktopApps = apps.filter((a) => a.enabled && a.installed && a.url);
  const desktopFiles = starredItems.filter((item) => item.workspaceId === currentWorkspaceId);

  const openSurface = (section: DeskSurfaceId) => {
    if (!currentWorkspaceId) return;
    setActivePanelSection(section);
    if (section === 'files') setActiveSource('my-drive');
    router.push(getWorkspacePath(currentWorkspaceId, `/${section}`));
  };

  return (
    <div className="flex h-full flex-col">
      <Header title={workspace?.name || 'Home'} />
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div
          className="absolute inset-0"
          style={wallpaperStyle(
            resolveDeskImageUrl(theme?.backgroundImageUrl),
            theme?.backgroundColor,
          )}
        />
        <div className="relative z-10 flex h-full w-full content-start flex-wrap items-start gap-x-7 gap-y-8 overflow-auto p-8">
          {surfaceIcons.map((section) => (
            <button
              key={section}
              type="button"
              className="flex w-[88px] flex-col items-center gap-3 text-white"
              onClick={() => openSurface(section)}
              title={section === 'chat' ? 'Chat' : 'Files'}
            >
              <span className="flex h-14 w-14 items-center justify-center bg-black/35 shadow-lg">
                {section === 'chat' ? <MessageSquare size={28} /> : <Folder size={28} />}
              </span>
              <span className="w-full truncate text-center text-[11px] font-medium leading-tight [text-shadow:0_1px_2px_rgba(0,0,0,0.8)]">
                {section === 'chat' ? 'Chat' : 'Files'}
              </span>
            </button>
          ))}
          {desktopApps.map((app) => (
            <button
              key={app.app_id}
              type="button"
              className="flex w-[88px] flex-col items-center gap-3 text-white"
              onClick={() => {
                if (!currentWorkspaceId) return;
                router.push(appsPath(currentWorkspaceId, app.app_id));
              }}
              title={app.name}
            >
              {app.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <span className="relative h-14 w-14 overflow-hidden p-0 shadow-lg">
                  <img
                    src={app.avatar_url}
                    alt=""
                    className="absolute inset-0 h-full w-full object-cover"
                  />
                </span>
              ) : (
                <span className="flex h-14 w-14 items-center justify-center bg-black/35 text-2xl shadow-lg">
                  {app.icon_emoji || app.name.slice(0, 1)}
                </span>
              )}
              <span className="w-full truncate text-center text-[11px] font-medium leading-tight [text-shadow:0_1px_2px_rgba(0,0,0,0.8)]">
                {app.name}
              </span>
            </button>
          ))}
          {desktopFiles.map((item) => (
            <button
              key={`${item.workspaceId}:${item.source}:${item.path}`}
              type="button"
              className="flex w-[88px] flex-col items-center gap-3 text-white"
              onClick={() => {
                if (item.type === 'folder') {
                  setStarredNavigation({ source: item.source, path: item.path });
                } else {
                  const parentPath = item.path.includes('/')
                    ? item.path.substring(0, item.path.lastIndexOf('/'))
                    : '';
                  setStarredNavigation({
                    source: item.source,
                    path: parentPath,
                    previewPath: item.path,
                  });
                }
                setActivePanelSection('files');
                router.push(
                  isMobile
                    ? filesBrowsePath(currentWorkspaceId)
                    : getWorkspacePath(currentWorkspaceId, '/files'),
                );
              }}
              title={item.path}
            >
              <span className="flex h-14 w-14 items-center justify-center bg-black/35 shadow-lg">
                {item.type === 'folder' ? <Folder size={28} /> : <File size={28} />}
              </span>
              <span className="w-full truncate text-center text-[11px] font-medium leading-tight [text-shadow:0_1px_2px_rgba(0,0,0,0.8)]">
                {item.name}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
