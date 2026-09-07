'use client';

import React, { useState } from 'react';
import { ChevronRight, File, Folder, HardDrive, RefreshCw, Server, Settings, Star } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { SidebarToolbarButton } from './sidebar-toolbar';
import { getWorkspacePath } from './utils';
import { filesBrowsePath } from '@/app/workspace/[workspaceId]/files/lib/files-route';
import { shellTokens } from '../tokens';

export function FilesSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const isMobilePanel = isMobile && !!detailOnly;
  const rowPadClass = isMobilePanel ? 'px-2 py-2.5 min-h-11' : 'px-2 py-1';
  const iconSize = isMobilePanel ? 14 : 12;
  const { currentWorkspaceId } = useWorkspaceStore();
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const platformDriveEnabled = Boolean(currentWorkspace?.platformDriveEnabled);
  const systemDriveEnabled = Boolean(currentWorkspace?.systemDriveEnabled);
  const workspaceRole = currentWorkspace?.currentUserRole;
  const isWorkspaceAdmin = workspaceRole === 'owner' || workspaceRole === 'admin';
  const [starredExpanded, setStarredExpanded] = useState(true);
  const {
    expandedCategories: fileExpandedCategories,
    toggleCategory: toggleFileCategory,
    activeSource,
    setActiveSource,
    syncedFolders,
    fetchFiles,
    fetchLocalFiles,
    refreshFiles,
    currentPath,
    loading,
    starredItems,
    unstarItem,
    setStarredNavigation,
  } = useFilesStore();

  const workspaceStarredItems = starredItems.filter(
    (i) => i.workspaceId === currentWorkspaceId
  );

  // Refresh the currently selected source — mirrors the Files page refresh action.
  const activeSyncedFolder = syncedFolders.find((f) => f.id === activeSource);
  const handleRefresh = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (activeSyncedFolder) {
      fetchLocalFiles(activeSyncedFolder.id, currentPath);
    } else {
      refreshFiles();
    }
  };

  const handleOpenDriveSettings = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    router.push(getWorkspacePath(currentWorkspaceId, '/settings/drives'));
  };

  const openFilesBrowser = () => {
    const target = isMobilePanel
      ? filesBrowsePath(currentWorkspaceId)
      : getWorkspacePath(currentWorkspaceId, '/files');
    router.push(target);
  };

  /** Load drive root before navigation so browse detail is never empty on first paint. */
  const openRemoteDrive = async (sourceId: string) => {
    setActiveSource(sourceId);
    await fetchFiles('', { limit: 50, offset: 0, search: '', workspaceId: currentWorkspaceId ?? undefined });
    openFilesBrowser();
  };

  const sectionActions = (
    <>
      <SidebarToolbarButton
        icon={<Settings size={14} />}
        label="Drive settings"
        onClick={handleOpenDriveSettings}
      />
      <SidebarToolbarButton
        icon={<RefreshCw size={14} />}
        label="Refresh"
        onClick={handleRefresh}
        disabled={loading}
        spinning={loading}
      />
    </>
  );

  return (
    <CollapsibleSection
      id="files"
      icon={<Folder size={18} />}
      label="Files"
      description="Workspace file storage"
      href={getWorkspacePath(currentWorkspaceId, '/files')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      {/* Header actions: drive settings + refresh selected source */}
      <div className="mb-1 flex items-center justify-start gap-0.5">
        {sectionActions}
      </div>

      {/* Local section */}
      <div className="space-y-0.5">
        <button
          onClick={() => toggleFileCategory('local')}
          className={cn(
            'flex w-full items-center gap-1 rounded-md px-1 py-1 hover:text-foreground',
            shellTokens.sidebar.sectionLabel,
          )}
        >
          <ChevronRight
            size={12}
            className={cn('transition-transform', fileExpandedCategories.includes('local') && 'rotate-90')}
          />
          <span className="flex-1 truncate text-left">Local</span>
          <span className="text-[10px]">{2 + (platformDriveEnabled ? 1 : 0) + (isWorkspaceAdmin && systemDriveEnabled ? 1 : 0) + syncedFolders.length}</span>
        </button>
        {fileExpandedCategories.includes('local') && (
          <div className="ml-3 space-y-0.5">
            <button
              onClick={() => openRemoteDrive('my-drive')}
              className={cn(
                'flex w-full items-center gap-2 rounded-md transition-colors',
                rowPadClass,
                shellTokens.sidebar.listRow,
                'hover:bg-workspace-accent-10',
                activeSource === 'my-drive' && 'bg-workspace-accent-15 text-workspace-accent'
              )}
            >
              <HardDrive size={iconSize} className="text-muted-foreground" />
              <span className="flex-1 truncate text-left">My Drive</span>
              {isMobilePanel && <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />}
            </button>

            <button
              onClick={() => openRemoteDrive('workspace')}
              className={cn(
                'flex w-full items-center gap-2 rounded-md transition-colors',
                rowPadClass,
                shellTokens.sidebar.listRow,
                'hover:bg-workspace-accent-10',
                activeSource === 'workspace' && 'bg-workspace-accent-15 text-workspace-accent'
              )}
            >
              <HardDrive size={iconSize} className="text-muted-foreground" />
              <span className="flex-1 truncate text-left">Workspace Drive</span>
              {isMobilePanel && <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />}
            </button>

            {platformDriveEnabled && (
              <button
                onClick={() => openRemoteDrive('platform-drive')}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md transition-colors',
                  rowPadClass,
                shellTokens.sidebar.listRow,
                  'hover:bg-workspace-accent-10',
                  activeSource === 'platform-drive' && 'bg-workspace-accent-15 text-workspace-accent'
                )}
                title="Files shared across every workspace where platform drive is enabled"
              >
                <HardDrive size={iconSize} className="text-muted-foreground" />
                <span className="flex-1 truncate text-left">Platform Drive</span>
                {isMobilePanel && <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />}
              </button>
            )}

            {isWorkspaceAdmin && systemDriveEnabled && (
              <button
                onClick={() => openRemoteDrive('system-drive')}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md transition-colors',
                  rowPadClass,
                shellTokens.sidebar.listRow,
                  'hover:bg-workspace-accent-10',
                  activeSource === 'system-drive' && 'bg-workspace-accent-15 text-workspace-accent'
                )}
                title="Full object storage tree — visible to workspace owners and admins"
              >
                <Server size={iconSize} className="text-muted-foreground" />
                <span className="flex-1 truncate text-left">System Drive</span>
                {isMobilePanel && <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />}
              </button>
            )}

            {syncedFolders.map((folder) => (
              <button
                key={folder.id}
                onClick={async () => {
                  setActiveSource(folder.id);
                  await fetchLocalFiles(folder.id);
                  openFilesBrowser();
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md transition-colors',
                  rowPadClass,
                shellTokens.sidebar.listRow,
                  'hover:bg-workspace-accent-10',
                  activeSource === folder.id && 'bg-workspace-accent-15 text-workspace-accent'
                )}
                title={folder.name}
              >
                <Folder size={iconSize} className="text-muted-foreground" />
                <span className="flex-1 truncate text-left">{folder.name}</span>
                {isMobilePanel && <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />}
              </button>
            ))}

          </div>
        )}
      </div>

      {/* Starred section */}
      <div className="mt-1 space-y-0.5">
        <button
          onClick={() => setStarredExpanded((v) => !v)}
          className={cn(
            'flex w-full items-center gap-1 rounded-md px-1 py-1 hover:text-foreground',
            shellTokens.sidebar.sectionLabel,
          )}
        >
          <ChevronRight
            size={12}
            className={cn('transition-transform', starredExpanded && 'rotate-90')}
          />
          <Star size={11} className="text-amber-400 fill-amber-400" />
          <span className="flex-1 truncate text-left">Starred</span>
          {workspaceStarredItems.length > 0 && (
            <span className="text-[10px]">{workspaceStarredItems.length}</span>
          )}
        </button>
        {starredExpanded && (
          <div className="ml-3 space-y-0.5">
            {workspaceStarredItems.length === 0 ? (
              <p className="px-2 py-1 text-[11px] text-muted-foreground">No starred items yet</p>
            ) : (
              workspaceStarredItems.map((item) => (
                <div
                  key={`${item.workspaceId}:${item.source}:${item.path}`}
                  className="group flex items-center gap-0.5"
                >
                  <button
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
                      router.push(
                        isMobilePanel
                          ? filesBrowsePath(currentWorkspaceId)
                          : getWorkspacePath(currentWorkspaceId, '/files')
                      );
                    }}
                    className={cn(
                      'flex flex-1 items-center gap-2 rounded-md transition-colors',
                      rowPadClass,
                      shellTokens.sidebar.listRow,
                      'hover:bg-workspace-accent-10',
                      activeSource === item.source && 'text-workspace-accent'
                    )}
                    title={item.path}
                  >
                    {item.type === 'folder' ? (
                      <Folder size={iconSize} className="flex-shrink-0 text-muted-foreground" />
                    ) : (
                      <File size={iconSize} className="flex-shrink-0 text-muted-foreground" />
                    )}
                    <span className="flex-1 truncate text-left">{item.name}</span>
                    {isMobilePanel && <ChevronRight size={18} className="flex-shrink-0 text-muted-foreground" />}
                  </button>
                  <button
                    title="Remove from starred"
                    onClick={() => unstarItem(item.path, item.workspaceId)}
                    className="hidden h-5 w-5 flex-shrink-0 items-center justify-center rounded text-amber-400 hover:text-amber-500 group-hover:flex"
                  >
                    <Star size={11} className="fill-current" />
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </CollapsibleSection>
  );
}
