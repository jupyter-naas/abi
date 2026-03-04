'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  FlaskConical, ChevronRight, Folder, FileCode, MoreVertical,
  FolderPlus, RefreshCw, ChevronsDownUp, Plus,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFilesStore, type FileInfo } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { usePrompt } from '@/components/ui/dialogs';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

const FileItem = React.memo(function FileItem({
  file,
  activeFile,
  selectedPath,
  onFileClick,
  onSelect,
  onRename,
  onDelete,
  depth = 0,
  fetchFolderContents,
}: {
  file: FileInfo;
  activeFile: string | null;
  selectedPath?: string | null;
  onFileClick: (path: string) => void;
  onSelect?: (path: string, isFolder: boolean) => void;
  onRename: (oldPath: string, newName: string) => void;
  onDelete: (path: string) => void;
  depth?: number;
  fetchFolderContents?: (folderPath: string) => Promise<FileInfo[]>;
}) {
  const isFolder = file.type === 'folder';
  const isActive = activeFile === file.path;
  const isSelected = selectedPath === file.path;
  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState<FileInfo[]>([]);
  const [loadingChildren, setLoadingChildren] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState(file.name);
  const [showMenu, setShowMenu] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const getRelativePath = (fullPath: string) => {
    const parts = fullPath.split('/');
    return parts.slice(1).join('/');
  };

  const handleToggleExpand = async () => {
    if (!isFolder) return;
    onSelect?.(file.path, true);

    if (!expanded && fetchFolderContents) {
      setLoadingChildren(true);
      const relativePath = getRelativePath(file.path);
      const contents = await fetchFolderContents(relativePath);
      setChildren(contents);
      setLoadingChildren(false);
    }
    setExpanded(!expanded);
  };

  const handleFileClick = () => {
    onSelect?.(file.path, false);
    onFileClick(file.path);
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      const lastDot = editName.lastIndexOf('.');
      if (lastDot > 0) {
        inputRef.current.setSelectionRange(0, lastDot);
      } else {
        inputRef.current.select();
      }
    }
  }, [isEditing]);

  const handleRename = () => {
    if (editName && editName !== file.name) {
      const parentPath = file.path.substring(0, file.path.lastIndexOf('/'));
      const newPath = parentPath ? `${parentPath}/${editName}` : editName;
      onRename(file.path, newPath);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRename();
    } else if (e.key === 'Escape') {
      setEditName(file.name);
      setIsEditing(false);
    }
  };

  const paddingLeft = depth * 12;

  return (
    <div>
      <div
        className={cn(
          'group relative flex w-full items-center gap-1 rounded-md py-1 pr-2 text-left text-sm transition-colors',
          'hover:bg-workspace-accent-10',
          isActive && 'bg-workspace-accent-15 text-workspace-accent',
          isSelected && !isActive && 'bg-muted/50'
        )}
        style={{ paddingLeft: `${paddingLeft + 8}px` }}
        onContextMenu={(e) => {
          e.preventDefault();
          setShowMenu(true);
        }}
      >
        <button
          onClick={isFolder ? handleToggleExpand : handleFileClick}
          className="flex flex-1 min-w-0 items-center gap-1.5 text-left overflow-hidden"
          title={file.name}
        >
          {isFolder ? (
            <>
              <ChevronRight
                size={12}
                className={cn(
                  'flex-shrink-0 transition-transform text-muted-foreground',
                  expanded && 'rotate-90',
                  loadingChildren && 'animate-pulse'
                )}
              />
              <Folder size={14} className="flex-shrink-0 text-muted-foreground" />
            </>
          ) : (
            <>
              <span className="w-3" />
              <FileCode size={14} className="flex-shrink-0 text-muted-foreground" />
            </>
          )}
          {isEditing ? (
            <input
              ref={inputRef}
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={handleRename}
              onKeyDown={handleKeyDown}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-background px-1 text-sm outline-none ring-1 ring-primary rounded"
            />
          ) : (
            <span className="flex-1 min-w-0 text-left">
              {(() => {
                const lastDot = file.name.lastIndexOf('.');
                if (lastDot > 0 && !isFolder) {
                  const name = file.name.substring(0, lastDot);
                  const ext = file.name.substring(lastDot);
                  return (
                    <span className="flex min-w-0">
                      <span className="truncate min-w-0">{name}</span>
                      <span className="flex-shrink-0">{ext}</span>
                    </span>
                  );
                }
                return <span className="truncate">{file.name}</span>;
              })()}
            </span>
          )}
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
          className="hidden h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted group-hover:flex"
        >
          <MoreVertical size={12} />
        </button>

        {showMenu && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setShowMenu(false)}
            />
            <div className="absolute right-0 top-full z-50 mt-1 min-w-[120px] rounded-md border bg-popover py-1 shadow-lg">
              <button
                onClick={() => {
                  setShowMenu(false);
                  setIsEditing(true);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted"
              >
                Rename
              </button>
              <button
                onClick={() => {
                  setShowMenu(false);
                  onDelete(file.path);
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10"
              >
                Delete
              </button>
            </div>
          </>
        )}
      </div>

      {isFolder && expanded && (
        <div>
          {loadingChildren ? (
            <div style={{ paddingLeft: `${paddingLeft + 20}px` }} className="py-1 text-xs text-muted-foreground">
              Loading...
            </div>
          ) : children.length > 0 ? (
            children.map((child) => (
              <FileItem
                key={child.path}
                file={child}
                activeFile={activeFile}
                selectedPath={selectedPath}
                onFileClick={onFileClick}
                onSelect={onSelect}
                onRename={onRename}
                onDelete={onDelete}
                depth={depth + 1}
                fetchFolderContents={fetchFolderContents}
              />
            ))
          ) : (
            <div style={{ paddingLeft: `${paddingLeft + 20}px` }} className="py-1 text-xs text-muted-foreground italic">
              Empty folder
            </div>
          )}
        </div>
      )}
    </div>
  );
});

export function LabSection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const [selectedLabPath, setSelectedLabPath] = useState<string | null>(null);
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    labFiles,
    labLoading,
    fetchLabFolderContents,
    refreshLabFiles,
    activeFile,
    openFile,
    createFile,
    createFolder,
    renameFile,
    deleteFile,
  } = useFilesStore();
  const { prompt, dialog: promptDialog } = usePrompt();

  const resolveTargetPath = useCallback((name: string) => {
    let targetPath = name;
    if (selectedLabPath) {
      const parts = selectedLabPath.split('/');
      const relativePath = parts.slice(1).join('/');
      const findItem = (files: FileInfo[], path: string): FileInfo | undefined => {
        for (const f of files) {
          if (f.path === path) return f;
        }
        return undefined;
      };
      const selectedItem = findItem(labFiles, selectedLabPath);
      if (selectedItem?.type === 'folder') {
        targetPath = `${relativePath}/${name}`;
      } else if (relativePath.includes('/')) {
        const parentPath = relativePath.substring(0, relativePath.lastIndexOf('/'));
        targetPath = `${parentPath}/${name}`;
      }
    }
    return targetPath;
  }, [selectedLabPath, labFiles]);

  const handleNewFile = useCallback(async () => {
    const name = await prompt({
      title: 'New File',
      description: 'Enter a name for the new file',
      defaultValue: 'untitled.py',
      confirmLabel: 'Create',
    });
    if (name) {
      const targetPath = resolveTargetPath(name);
      const result = await createFile(targetPath);
      if (result) {
        await refreshLabFiles();
        openFile(result.path);
        router.push(getWorkspacePath(currentWorkspaceId, '/lab'));
      }
    }
  }, [prompt, resolveTargetPath, createFile, refreshLabFiles, openFile, router, currentWorkspaceId]);

  const handleNewFolder = useCallback(async () => {
    const name = await prompt({
      title: 'New Folder',
      description: 'Enter a name for the new folder',
      defaultValue: 'new-folder',
      confirmLabel: 'Create',
    });
    if (name) {
      const targetPath = resolveTargetPath(name);
      await createFolder(targetPath);
      await refreshLabFiles();
    }
  }, [prompt, resolveTargetPath, createFolder, refreshLabFiles]);

  return (
    <>
    {promptDialog}
    <CollapsibleSection
      id="lab"
      icon={<FlaskConical size={18} />}
      label="Lab"
      description="Embedded development environment"
      href={getWorkspacePath(currentWorkspaceId, '/lab')}
      collapsed={collapsed}
    >
      {/* File explorer toolbar */}
      <div className="flex items-center gap-0.5 px-1 pb-1">
        <button
          onClick={handleNewFile}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="New File"
        >
          <FileCode size={14} />
        </button>
        <button
          onClick={handleNewFolder}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="New Folder"
        >
          <FolderPlus size={14} />
        </button>
        <button
          onClick={() => refreshLabFiles()}
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
            labLoading && "animate-spin"
          )}
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
        <button
          onClick={() => {}}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Collapse All"
        >
          <ChevronsDownUp size={14} />
        </button>
      </div>

      {/* File tree */}
      {labFiles.length > 0 ? (
        <div className="space-y-0.5">
          {labFiles.map((file) => (
            <FileItem
              key={file.path}
              file={file}
              activeFile={activeFile}
              selectedPath={selectedLabPath}
              onFileClick={(path) => {
                openFile(path);
                router.push(getWorkspacePath(currentWorkspaceId, '/lab'));
              }}
              onSelect={(path) => setSelectedLabPath(path)}
              onRename={async (oldPath, newPath) => {
                await renameFile(oldPath, newPath);
                await refreshLabFiles();
              }}
              onDelete={async (path) => {
                await deleteFile(path);
                await refreshLabFiles();
              }}
              depth={0}
              fetchFolderContents={fetchLabFolderContents}
            />
          ))}
        </div>
      ) : (
        <p className="px-2 py-2 text-xs text-muted-foreground">
          {labLoading ? 'Loading...' : 'No files yet'}
        </p>
      )}
    </CollapsibleSection>
    </>
  );
}
