'use client';

import React, { useState } from 'react';
import { ChevronRight, File, Folder, HardDrive, RefreshCw, Server, Settings, Star } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { SidebarToolbarButton } from './sidebar-toolbar';
import { getWorkspacePath } from './utils';

export function FilesSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
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
          className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
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
              onClick={() => {
                setActiveSource('my-drive');
                router.push(getWorkspacePath(currentWorkspaceId, '/files'));
              }}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors',
                'hover:bg-workspace-accent-10',
                activeSource === 'my-drive' && 'bg-workspace-accent-15 text-workspace-accent'
              )}
            >
              <HardDrive size={12} className="text-muted-foreground" />
              <span className="flex-1 truncate text-left">My Drive</span>
            </button>

            <button
              onClick={() => {
                setActiveSource('workspace');
                router.push(getWorkspacePath(currentWorkspaceId, '/files'));
              }}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors',
                'hover:bg-workspace-accent-10',
                activeSource === 'workspace' && 'bg-workspace-accent-15 text-workspace-accent'
              )}
            >
              <HardDrive size={12} className="text-muted-foreground" />
              <span className="flex-1 truncate text-left">Workspace Drive</span>
            </button>

            {platformDriveEnabled && (
              <button
                onClick={() => {
                  setActiveSource('platform-drive');
                  router.push(getWorkspacePath(currentWorkspaceId, '/files'));
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors',
                  'hover:bg-workspace-accent-10',
                  activeSource === 'platform-drive' && 'bg-workspace-accent-15 text-workspace-accent'
                )}
                title="Files shared across every workspace where platform drive is enabled"
              >
                <HardDrive size={12} className="text-muted-foreground" />
                <span className="flex-1 truncate text-left">Platform Drive</span>
              </button>
            )}

            {isWorkspaceAdmin && systemDriveEnabled && (
              <button
                onClick={() => {
                  setActiveSource('system-drive');
                  router.push(getWorkspacePath(currentWorkspaceId, '/files'));
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors',
                  'hover:bg-workspace-accent-10',
                  activeSource === 'system-drive' && 'bg-workspace-accent-15 text-workspace-accent'
                )}
                title="Full object storage tree — visible to workspace owners and admins"
              >
                <Server size={12} className="text-muted-foreground" />
                <span className="flex-1 truncate text-left">System Drive</span>
              </button>
            )}

            {syncedFolders.map((folder) => (
              <button
                key={folder.id}
                onClick={async () => {
                  setActiveSource(folder.id);
                  await fetchLocalFiles(folder.id);
                  router.push(getWorkspacePath(currentWorkspaceId, '/files'));
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors',
                  'hover:bg-workspace-accent-10',
                  activeSource === folder.id && 'bg-workspace-accent-15 text-workspace-accent'
                )}
                title={folder.name}
              >
                <Folder size={12} className="text-muted-foreground" />
                <span className="flex-1 truncate text-left">{folder.name}</span>
              </button>
            ))}

          </div>
        )}
      </div>

      {/* Starred section */}
      <div className="mt-1 space-y-0.5">
        <button
          onClick={() => setStarredExpanded((v) => !v)}
          className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
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
                      const filesPath = getWorkspacePath(currentWorkspaceId, '/files');
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
                      router.push(filesPath);
                    }}
                    className={cn(
                      'flex flex-1 items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors',
                      'hover:bg-workspace-accent-10',
                      activeSource === item.source && 'text-workspace-accent'
                    )}
                    title={item.path}
                  >
                    {item.type === 'folder' ? (
                      <Folder size={12} className="flex-shrink-0 text-muted-foreground" />
                    ) : (
                      <File size={12} className="flex-shrink-0 text-muted-foreground" />
                    )}
                    <span className="flex-1 truncate text-left">{item.name}</span>
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
