'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Terminal, ChevronRight, Folder, FileCode, MoreVertical,
  FolderPlus, RefreshCw, Plus, Trash2, Pencil, PackagePlus,
  Code2,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useFilesStore, type FileInfo } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { usePrompt } from '@/components/ui/dialogs';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';


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

  // Re-fetch children when the tree version bumps (triggered by refreshFsFiles)
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
  label, icon, files, loading, activeFile, selectedPath, onFileClick, onSelect,
  onRename, onDelete, fetchFolderContents,
  onNewFile, onNewFolder, onRefresh, onNewModule, diffs, treeVersion, sandboxRoot,
}: {
  label: string;
  icon: React.ReactNode;
  files: FileInfo[];
  loading: boolean;
  activeFile: string | null;
  selectedPath: string | null;
  onFileClick: (path: string) => void;
  onSelect: (path: string) => void;
  onRename: (oldPath: string, newPath: string) => void;
  onDelete: (path: string) => void;
  fetchFolderContents?: (path: string) => Promise<FileInfo[]>;
  onNewFile?: () => void;
  onNewFolder?: () => void;
  onRefresh?: () => void;
  onNewModule?: () => void;
  diffs?: Record<string, DiffInfo>;
  treeVersion?: number;
  sandboxRoot?: string;  // paths outside this prefix are read-only
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="px-2 pb-2">
      {/* Header row: toggle on the left, action buttons on the right — siblings, not nested */}
      <div className="mb-1 flex items-center gap-1.5 px-1">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground"
        >
          <ChevronRight size={10} className={cn('flex-shrink-0 transition-transform', open && 'rotate-90')} />
          <span className="flex items-center gap-1 truncate">{icon}{label}</span>
        </button>
        <div className="ml-auto flex flex-shrink-0 items-center gap-0.5">
          {onNewModule && (
            <button onClick={onNewModule} className="flex h-4 w-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground" title="New module">
              <PackagePlus size={11} />
            </button>
          )}
          {onNewFile && (
            <button onClick={onNewFile} className="flex h-4 w-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground" title="New file">
              <FileCode size={11} />
            </button>
          )}
          {onNewFolder && (
            <button onClick={onNewFolder} className="flex h-4 w-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground" title="New folder">
              <FolderPlus size={11} />
            </button>
          )}
          {onRefresh && (
            <button onClick={onRefresh} className={cn('flex h-4 w-4 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground', loading && 'animate-spin')} title="Refresh">
              <RefreshCw size={11} />
            </button>
          )}
        </div>
      </div>

      {open && (
        <div className="space-y-0.5">
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
      )}
    </div>
  );
}

// ─── Code section ─────────────────────────────────────────────────────────────

export function CodeSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const router = useRouter();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [sandboxRoot, setSandboxRoot] = useState<string>('sandbox');
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    fsFiles, fsLoading, fsActiveFile, fsFolderContents,
    fetchFsFiles, fetchFsFolderContents, refreshFsFiles,
    openFsFile, createFsFile, createFsFolder, deleteFsFile,
    fsDiffs, fsTreeVersion,
  } = useFilesStore();
  const { prompt, dialog: promptDialog } = usePrompt();

  // Load filesystem root on first mount; capture sandbox_root from response
  useEffect(() => {
    if (fsFiles.length === 0 && !fsLoading) {
      fetchFsFiles().then(() => {
        const sr = useFilesStore.getState().fsSandboxRoot;
        if (sr) setSandboxRoot(sr);
      });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const navigateToCode = () => router.push(getWorkspacePath(currentWorkspaceId, '/code'));

  // Resolve target path for new file/folder relative to current selection
  const resolveTarget = useCallback((name: string) => {
    if (!selectedPath) return name;
    // Find if selected is a folder anywhere in the cached tree
    const allFiles = [
      ...fsFiles,
      ...Object.values(fsFolderContents).flat(),
    ];
    const item = allFiles.find((f) => f.path === selectedPath);
    if (item?.type === 'folder') return `${selectedPath}/${name}`;
    const parent = selectedPath.substring(0, selectedPath.lastIndexOf('/'));
    return parent ? `${parent}/${name}` : name;
  }, [selectedPath, fsFiles, fsFolderContents]);

  // fetchFsFolderContents receives the full path from FileNode (no stripping needed)
  const fetchFolderContents = useCallback(
    (path: string) => fetchFsFolderContents(path),
    [fetchFsFolderContents]
  );

  const handleNewFile = useCallback(async () => {
    const name = await prompt({ title: 'New File', description: 'Enter file name', defaultValue: 'untitled.py', confirmLabel: 'Create' });
    if (name) {
      const targetPath = resolveTarget(name);
      const ok = await createFsFile(targetPath);
      if (ok) { openFsFile(targetPath); navigateToCode(); }
    }
  }, [prompt, resolveTarget, createFsFile, openFsFile]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNewFolder = useCallback(async () => {
    const name = await prompt({ title: 'New Folder', description: 'Enter folder name', defaultValue: 'my-folder', confirmLabel: 'Create' });
    if (name) await createFsFolder(resolveTarget(name));
  }, [prompt, resolveTarget, createFsFolder]);

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
      await createFsFolder(base);
      await createFsFile(`${base}/__init__.py`);
      await createFsFile(`${base}/README.md`);
      openFsFile(`${base}/__init__.py`);
      navigateToCode();
    }
  }, [prompt, resolveTarget, createFsFolder, createFsFile, openFsFile]); // eslint-disable-line react-hooks/exhaustive-deps

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
        <TreePanel
          label="Explorer"
          icon={<Code2 size={10} />}
          files={fsFiles}
          loading={fsLoading}
          activeFile={fsActiveFile}
          selectedPath={selectedPath}
          onFileClick={(path) => { openFsFile(path); navigateToCode(); }}
          onSelect={(p) => setSelectedPath(p)}
          onRename={async (oldPath, newPath) => {
            await useFilesStore.getState().renameFsFile(oldPath, newPath);
          }}
          onDelete={async (p) => { await deleteFsFile(p); }}
          fetchFolderContents={fetchFolderContents}
          onNewFile={handleNewFile}
          onNewFolder={handleNewFolder}
          onRefresh={refreshFsFiles}
          onNewModule={handleNewModule}
          diffs={fsDiffs}
          treeVersion={fsTreeVersion}
          sandboxRoot={sandboxRoot}
        />
      </CollapsibleSection>
    </>
  );
}
