'use client';

import React from 'react';
import { ChevronRight, Folder, Plus, HardDrive, Upload, Cloud, Database } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

const StorageSourceItem = React.memo(function StorageSourceItem({
  source,
  isActive,
  onClick,
}: {
  source: { id: string; name: string; icon: string; connected: boolean; description?: string };
  isActive: boolean;
  onClick: () => void;
}) {
  const iconMap: Record<string, React.ReactNode> = {
    'hard-drive': <HardDrive size={14} />,
    'upload': <Upload size={14} />,
    'cloud': <Cloud size={14} />,
    'database': <Database size={14} />,
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-sm transition-colors',
        'hover:bg-workspace-accent-10',
        isActive && 'bg-workspace-accent-15 text-workspace-accent',
        !source.connected && 'opacity-50'
      )}
    >
      <span className="text-muted-foreground">{iconMap[source.icon] || <Folder size={14} />}</span>
      <span className="flex-1 truncate text-left">{source.name}</span>
      {!source.connected && (
        <span className="text-[10px] text-muted-foreground">Not connected</span>
      )}
    </button>
  );
});

const StorageCategoryGroup = React.memo(function StorageCategoryGroup({
  label,
  sources,
  isExpanded,
  onToggle,
  activeSource,
  onSelectSource,
  onAddSource,
}: {
  label: string;
  sources: { id: string; name: string; icon: string; connected: boolean; description?: string }[];
  isExpanded: boolean;
  onToggle: () => void;
  activeSource: string;
  onSelectSource: (id: string) => void;
  onAddSource?: () => void;
}) {
  const connectedSources = sources.filter((s) => s.connected);
  const availableSources = sources.filter((s) => !s.connected);

  return (
    <div className="space-y-0.5">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronRight
          size={12}
          className={cn('transition-transform', isExpanded && 'rotate-90')}
        />
        <span className="flex-1 truncate text-left">{label}</span>
        <span className="text-[10px]">
          {connectedSources.length}
        </span>
      </button>
      {isExpanded && (
        <div className="ml-3 space-y-0.5">
          {connectedSources.map((source) => (
            <StorageSourceItem
              key={source.id}
              source={source}
              isActive={activeSource === source.id}
              onClick={() => onSelectSource(source.id)}
            />
          ))}

          {connectedSources.length === 0 && (
            <div className="px-2 py-1 text-xs text-muted-foreground">
              No sources connected
            </div>
          )}

          {onAddSource && availableSources.length > 0 && (
            <button
              onClick={onAddSource}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Plus size={12} />
              <span>Connect {label}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
});

export function FilesSection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    storageSources,
    expandedCategories: fileExpandedCategories,
    toggleCategory: toggleFileCategory,
    activeSource,
    setActiveSource,
    syncedFolders,
    syncLocalFolder,
    fetchLocalFiles,
  } = useFilesStore();

  const cloudSources = storageSources.filter((s) => s.category === 'cloud');

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
          <span className="text-[10px]">{1 + syncedFolders.length}</span>
        </button>
        {fileExpandedCategories.includes('local') && (
          <div className="ml-3 space-y-0.5">
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
              <span className="flex-1 truncate text-left">Workspace</span>
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

            <button
              onClick={async () => {
                const folder = await syncLocalFolder();
                if (folder) {
                  router.push(getWorkspacePath(currentWorkspaceId, '/files'));
                }
              }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Plus size={12} />
              <span>Sync Folder</span>
            </button>
          </div>
        )}
      </div>

      {/* Cloud Sources */}
      <StorageCategoryGroup
        label="Cloud"
        sources={cloudSources}
        isExpanded={fileExpandedCategories.includes('cloud')}
        onToggle={() => toggleFileCategory('cloud')}
        activeSource={activeSource}
        onSelectSource={(id) => {
          setActiveSource(id);
          router.push(getWorkspacePath(currentWorkspaceId, '/files'));
        }}
        onAddSource={() => router.push(getWorkspacePath(currentWorkspaceId, '/settings/storage'))}
      />
    </CollapsibleSection>
  );
}
