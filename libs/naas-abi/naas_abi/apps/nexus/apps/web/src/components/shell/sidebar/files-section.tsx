'use client';

import React from 'react';
import { ChevronRight, Folder, HardDrive } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

export function FilesSection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    expandedCategories: fileExpandedCategories,
    toggleCategory: toggleFileCategory,
    activeSource,
    setActiveSource,
    syncedFolders,
    fetchLocalFiles,
  } = useFilesStore();

  return (
    <CollapsibleSection
      id="files"
      icon={<Folder size={18} />}
      label="Files"
      description="Workspace file storage"
      href={getWorkspacePath(currentWorkspaceId, '/files')}
      collapsed={collapsed}
    >
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
          <span className="text-[10px]">{2 + syncedFolders.length}</span>
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
    </CollapsibleSection>
  );
}
