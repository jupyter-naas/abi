'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Terminal, ChevronRight, Folder, FileCode, MoreVertical,
  FolderPlus, RefreshCw, Plus, Trash2, Pencil, PackagePlus,
  GitCompare,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFilesStore, type FileInfo, CODE_MY_DRIVE_FOLDER, resolveCodePath } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { usePrompt } from '@/components/ui/dialogs';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import {
  OpencodeChangesList,
} from '@/components/code/code-sidebar-panels';
import { useOpencodeSessionStore } from '@/stores/opencode-session';


// ─── Generic file tree node ───────────────────────────────────────────────────

type DiffInfo = { additions: number; deletions: number; status: string };

const FileNode = React.memo(function FileNode({
  file, activeFile, selectedPath, onFileClick, onSelect, onRename, onDelete,
  depth = 0, fetchFolderContents, readOnly = false, diffs, treeVersion,
}: {
  file: FileInfo; activeFile: string | null; selectedPath?: string | null;
  onFileClick: (path: string) => void;
  onSelect?: (path: string, isFolder: boolean) => void;
  onRename: (oldPath: string, newName: string) => void;
  onDelete: (path: string) => void;
  depth?: number;
  fetchFolderContents?: (folderPath: string) => Promise<FileInfo[]>;
  readOnly?: boolean;
  diffs?: Record<string, DiffInfo>;
  treeVersion?: number;
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

  // Diff decoration: match by filename or full path suffix
  const diff = diffs
    ? (diffs[file.path] ?? Object.entries(diffs).find(([k]) => file.path.endsWith(k) || k.endsWith(file.path))?.[1])
    : undefined;

  // Re-fetch children when the tree version bumps (triggered by refreshCodeFiles)
  useEffect(() => {
    if (isFolder && expanded && fetchFolderContents && treeVersion !== undefined) {
      fetchFolderContents(file.path).then((data) => setChildren(data));
    }
  }, [treeVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async () => {
    if (!isFolder) return;
    onSelect?.(file.path, true);
    if (!expanded && fetchFolderContents) {
      setLoadingChildren(true);
      // Pass the full path; the caller's fetchFolderContents decides what to do with it
      const data = await fetchFolderContents(file.path);
      setChildren(data);
      setLoadingChildren(false);
    }
    setExpanded((v) => !v);
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      const dot = editName.lastIndexOf('.');
      if (dot > 0) inputRef.current.setSelectionRange(0, dot);
      else inputRef.current.select();
    }
  }, [isEditing]);

  const commitRename = () => {
    if (editName && editName !== file.name) {
      const parent = file.path.substring(0, file.path.lastIndexOf('/'));
      onRename(file.path, parent ? `${parent}/${editName}` : editName);
    }
    setIsEditing(false);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') commitRename();
    if (e.key === 'Escape') { setEditName(file.name); setIsEditing(false); }
  };

  return (
    <div>
      <div
        className={cn(
          'group relative flex w-full items-center gap-1 rounded-md py-[3px] pr-1 text-left text-xs transition-colors',
          'hover:bg-workspace-accent-10',
          isActive && 'bg-workspace-accent-15 text-workspace-accent',
          isSelected && !isActive && 'bg-muted/50'
        )}
        style={{ paddingLeft: `${depth * 10 + 6}px` }}
        onContextMenu={(e) => { if (!readOnly) { e.preventDefault(); setShowMenu(true); } }}
      >
        <button onClick={isFolder ? toggle : () => { onSelect?.(file.path, false); onFileClick(file.path); }}
          className="flex flex-1 min-w-0 items-center gap-1 text-left overflow-hidden"
        >
          {isFolder ? (
            <>
              <ChevronRight size={11} className={cn('flex-shrink-0 transition-transform text-muted-foreground', expanded && 'rotate-90', loadingChildren && 'animate-pulse')} />
              <Folder size={12} className="flex-shrink-0 text-muted-foreground" />
            </>
          ) : (
            <><span className="w-2.5" /><FileCode size={12} className="flex-shrink-0 text-muted-foreground" /></>
          )}
          {isEditing ? (
            <input ref={inputRef} type="text" value={editName} onChange={(e) => setEditName(e.target.value)}
              onBlur={commitRename} onKeyDown={onKey} onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-background px-1 text-xs outline-none ring-1 ring-primary rounded" />
          ) : (
            <span className={cn(
              'flex-1 min-w-0 truncate',
              diff?.status === 'added' && 'text-emerald-500 dark:text-emerald-400',
              diff?.status === 'modified' && 'text-amber-500 dark:text-amber-400',
              diff?.status === 'deleted' && 'text-red-500 line-through opacity-60',
            )}>{file.name}</span>
          )}
          {diff && !isEditing && (
            <span className="ml-1 flex-shrink-0 font-mono text-[9px] leading-none opacity-80">
              {diff.additions > 0 && <span className="text-emerald-500">+{diff.additions}</span>}
              {diff.deletions > 0 && <span className="ml-0.5 text-red-400">-{diff.deletions}</span>}
            </span>
          )}
        </button>

        {!readOnly && (
          <button onClick={(e) => { e.stopPropagation(); setShowMenu((v) => !v); }}
            className="hidden h-4 w-4 items-center justify-center rounded text-muted-foreground hover:bg-muted group-hover:flex">
            <MoreVertical size={10} />
          </button>
        )}

        {showMenu && !readOnly && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
            <div className="absolute right-0 top-full z-50 mt-1 min-w-[110px] rounded-md border bg-popover py-1 shadow-lg">
              <button onClick={() => { setShowMenu(false); setIsEditing(true); }} className="flex w-full items-center gap-1.5 px-3 py-1.5 text-xs hover:bg-muted">
                <Pencil size={11} /> Rename
              </button>
              <button onClick={() => { setShowMenu(false); onDelete(file.path); }} className="flex w-full items-center gap-1.5 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10">
                <Trash2 size={11} /> Delete
              </button>
            </div>
          </>
        )}
      </div>

      {isFolder && expanded && (
        <div>
          {loadingChildren ? (
            <div style={{ paddingLeft: `${depth * 10 + 16}px` }} className="py-1 text-[11px] text-muted-foreground">Loading...</div>
          ) : children.length > 0 ? (
            children.map((c) => (
              <FileNode key={c.path} file={c} activeFile={activeFile} selectedPath={selectedPath}
                onFileClick={onFileClick} onSelect={onSelect} onRename={onRename} onDelete={onDelete}
                depth={depth + 1} fetchFolderContents={fetchFolderContents}
                readOnly={readOnly}
                diffs={diffs} treeVersion={treeVersion} />
            ))
          ) : (
            <div style={{ paddingLeft: `${depth * 10 + 16}px` }} className="py-1 text-[11px] text-muted-foreground italic">Empty</div>
          )}
        </div>
      )}
    </div>
  );
});

// ─── Tree panel ───────────────────────────────────────────────────────────────

function TreePanel({
  files, loading, activeFile, selectedPath, onFileClick, onSelect,
  onRename, onDelete, fetchFolderContents,
  diffs, treeVersion, sandboxRoot,
}: {
  files: FileInfo[];
  loading: boolean;
  activeFile: string | null;
  selectedPath: string | null;
  onFileClick: (path: string) => void;
  onSelect: (path: string) => void;
  onRename: (oldPath: string, newPath: string) => void;
  onDelete: (path: string) => void;
  fetchFolderContents?: (path: string) => Promise<FileInfo[]>;
  diffs?: Record<string, DiffInfo>;
  treeVersion?: number;
  sandboxRoot?: string;
}) {
  return (
    <div className="space-y-0.5 overflow-y-auto">
      {files.length > 0 ? (
        files.map((f) => (
          <FileNode key={f.path} file={f} activeFile={activeFile} selectedPath={selectedPath}
            onFileClick={onFileClick} onSelect={(p) => onSelect(p)} onRename={onRename} onDelete={onDelete}
            depth={0} fetchFolderContents={fetchFolderContents}
            readOnly={sandboxRoot ? !f.path.startsWith(sandboxRoot) : false}
            diffs={diffs} treeVersion={treeVersion} />
        ))
      ) : (
        <p className="px-2 py-1 text-[11px] text-muted-foreground italic">
          {loading ? 'Loading...' : 'No files yet — create your first module'}
        </p>
      )}
    </div>
  );
}

// ─── Code section ─────────────────────────────────────────────────────────────

type CodeSidebarView = 'explorer' | 'changes';

export function CodeSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [codeRoot, setCodeRoot] = useState<string>('');
  const [sidebarView, setSidebarView] = useState<CodeSidebarView>('explorer');
  const [refreshingChanges, setRefreshingChanges] = useState(false);
  const { currentWorkspaceId } = useWorkspaceStore();
  const { opencodeSessionId, fetchSessionDiff } = useOpencodeSessionStore();
  const {
    codeFiles, codeLoading, codeActiveFile, codeFolderContents,
    fetchCodeFiles, fetchCodeFolderContents, refreshCodeFiles,
    openCodeFile, createCodeFile, createCodeFolder, deleteCodeFile,
    codeDiffs, localChanges, codeTreeVersion, syncCodeWorkdir,
  } = useFilesStore();
  const { prompt, dialog: promptDialog } = usePrompt();

  // Load the sandbox subtree on mount — we only expose the writable sandbox
  useEffect(() => {
    void syncCodeWorkdir('pull');
    void fetchCodeFiles(CODE_MY_DRIVE_FOLDER);
  }, [fetchCodeFiles, syncCodeWorkdir]);

  useEffect(() => {
    const root = useFilesStore.getState().codeRoot;
    if (root) setCodeRoot(root);
  }, [codeFiles, codeLoading]);

  const navigateToCode = () => router.push(getWorkspacePath(currentWorkspaceId, '/code'));

  const resolveTarget = useCallback(
    (name: string) => resolveCodePath(name, selectedPath),
    [selectedPath],
  );

  // fetchFsFolderContents receives the full path from FileNode (no stripping needed)
  const fetchFolderContents = useCallback(
    (path: string) => fetchCodeFolderContents(path),
    [fetchCodeFolderContents]
  );

  const handleNewFile = useCallback(async () => {
    const name = await prompt({ title: 'New File', description: 'Enter file name', defaultValue: 'untitled.py', confirmLabel: 'Create' });
    if (name) {
      const targetPath = resolveTarget(name);
      const createdPath = await createCodeFile(targetPath);
      if (createdPath) { openCodeFile(createdPath); navigateToCode(); }
    }
  }, [prompt, resolveTarget, createCodeFile, openCodeFile]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNewFolder = useCallback(async () => {
    const name = await prompt({ title: 'New Folder', description: 'Enter folder name', defaultValue: 'my-folder', confirmLabel: 'Create' });
    if (name) await createCodeFolder(resolveTarget(name));
  }, [prompt, resolveTarget, createCodeFolder]);

  const handleNewModule = useCallback(async () => {
    const name = await prompt({
      title: 'New Module',
      description: 'Module name — creates a scaffolded folder with __init__.py and README.md',
      defaultValue: 'my-module',
      confirmLabel: 'Create',
    });
    if (name) {
      const slug = name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
      const base = resolveTarget(slug);
      await createCodeFolder(base);
      const initPath = await createCodeFile(`${base}/__init__.py`);
      await createCodeFile(`${base}/README.md`);
      if (initPath) openCodeFile(initPath);
      navigateToCode();
    }
  }, [prompt, resolveTarget, createCodeFolder, createCodeFile, openCodeFile]); // eslint-disable-line react-hooks/exhaustive-deps

  const changeCount = new Set([...Object.keys(codeDiffs), ...Object.keys(localChanges)]).size;

  const handleRefreshChanges = async () => {
    setRefreshingChanges(true);
    try {
      await fetchSessionDiff(opencodeSessionId);
    } finally {
      setRefreshingChanges(false);
    }
  };

  return (
    <>
      {promptDialog}
      <CollapsibleSection
        id="code"
        icon={<Terminal size={18} />}
        label="Code"
        description="Development environment"
        href={getWorkspacePath(currentWorkspaceId, '/code')}
        collapsed={collapsed}
        detailOnly={detailOnly}
      >
        <div className="px-2 pb-2">
          {/* View toggle — full width */}
          <div className="mb-1 flex rounded-md bg-muted/50 p-0.5">
            <button
              type="button"
              onClick={() => setSidebarView('explorer')}
              className={cn(
                'flex flex-1 items-center justify-center gap-1 rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wide transition-colors',
                sidebarView === 'explorer'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Folder size={10} />
              Explorer
            </button>
            <button
              type="button"
              onClick={() => setSidebarView('changes')}
              className={cn(
                'flex flex-1 items-center justify-center gap-1 rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wide transition-colors',
                sidebarView === 'changes'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <GitCompare size={10} />
              Changes
              {changeCount > 0 && (
                <span className="rounded-full bg-primary/15 px-1 py-px text-[9px] font-bold text-primary">
                  {changeCount}
                </span>
              )}
            </button>
          </div>

          {/* Action buttons — right-aligned below toggle */}
          <div className="mb-1.5 flex items-center justify-end gap-0.5 px-0.5">
            {sidebarView === 'explorer' ? (
              <>
                <button
                  type="button"
                  onClick={() => void handleNewModule()}
                  className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="New module"
                >
                  <PackagePlus size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => void handleNewFile()}
                  className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="New file"
                >
                  <FileCode size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => void handleNewFolder()}
                  className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="New folder"
                >
                  <FolderPlus size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => void refreshCodeFiles()}
                  className={cn(
                    'flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground',
                    codeLoading && 'animate-spin',
                  )}
                  title="Refresh"
                >
                  <RefreshCw size={12} />
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => void handleRefreshChanges()}
                className={cn(
                  'flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground',
                  refreshingChanges && 'animate-spin',
                )}
                title="Refresh changes"
              >
                <RefreshCw size={12} />
              </button>
            )}
          </div>

          {sidebarView === 'explorer' ? (
            <TreePanel
              files={codeFiles}
              loading={codeLoading}
              activeFile={codeActiveFile}
              selectedPath={selectedPath}
              onFileClick={(path) => { openCodeFile(path); navigateToCode(); }}
              onSelect={(p) => setSelectedPath(p)}
              onRename={async (oldPath, newPath) => {
                await useFilesStore.getState().renameCodeFile(oldPath, newPath);
              }}
              onDelete={async (p) => { await deleteCodeFile(p); }}
              fetchFolderContents={fetchFolderContents}
              diffs={codeDiffs}
              treeVersion={codeTreeVersion}
              sandboxRoot={codeRoot}
            />
          ) : (
            <OpencodeChangesList
              onOpenFile={(path) => {
                void useFilesStore.getState().openCodeFileDiff(path);
                navigateToCode();
              }}
            />
          )}
        </div>
      </CollapsibleSection>
    </>
  );
}
