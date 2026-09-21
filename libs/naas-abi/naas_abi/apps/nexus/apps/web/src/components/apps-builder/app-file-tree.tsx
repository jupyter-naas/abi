'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, File as FileIcon, FilePlus, Folder, Trash2 } from 'lucide-react';
import { buildFileTree, type AppProjectFile, type FileTreeNode } from '@/lib/app-projects';
import { cn } from '@/lib/utils';

type Props = {
  files: AppProjectFile[];
  selected: string | null;
  dirtyPaths: Set<string>;
  entry: string | null;
  onSelect: (path: string) => void;
  onCreate: () => void;
  onDelete: (path: string) => void;
};

function formatSize(size?: number): string {
  if (size === undefined) return '';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/** The app project's files (left column of the Apps editor). */
export function AppFileTree({ files, selected, dirtyPaths, entry, onSelect, onCreate, onDelete }: Props) {
  const tree = useMemo(() => buildFileTree(files), [files]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  const render = (nodes: FileTreeNode[], depth: number) =>
    nodes.map((node) => {
      const pad = { paddingLeft: `${8 + depth * 12}px` };
      if (node.children) {
        const open = !collapsed.has(node.path);
        return (
          <div key={node.path}>
            <button
              type="button"
              onClick={() => toggle(node.path)}
              className="flex w-full items-center gap-1 py-1 pr-2 text-left text-xs text-muted-foreground hover:bg-muted/60"
              style={pad}
            >
              {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              <Folder size={12} className="shrink-0" />
              <span className="truncate">{node.name}</span>
            </button>
            {open && render(node.children, depth + 1)}
          </div>
        );
      }
      const active = node.path === selected;
      return (
        <div
          key={node.path}
          className={cn(
            'group flex items-center gap-1 pr-1 text-xs',
            active ? 'bg-workspace-accent-10 text-foreground' : 'text-foreground/80 hover:bg-muted/60',
          )}
          style={pad}
        >
          <button
            type="button"
            onClick={() => onSelect(node.path)}
            title={`${node.path} · ${formatSize(node.size)}`}
            className="flex min-w-0 flex-1 items-center gap-1 py-1 text-left"
          >
            <FileIcon size={12} className="ml-3 shrink-0 text-muted-foreground" />
            <span className={cn('truncate', node.path === entry && 'font-semibold')}>{node.name}</span>
            {dirtyPaths.has(node.path) && (
              <span className="ml-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" aria-label="unsaved" />
            )}
          </button>
          <button
            type="button"
            onClick={() => onDelete(node.path)}
            title={`Delete ${node.path}`}
            className="invisible rounded p-0.5 text-muted-foreground hover:text-red-600 group-hover:visible"
          >
            <Trash2 size={11} />
          </button>
        </div>
      );
    });

  return (
    <div className="flex h-full min-h-0 flex-col border-r border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-2 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Files
        </span>
        <button
          type="button"
          onClick={onCreate}
          title="New file"
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <FilePlus size={13} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto py-1">{render(tree, 0)}</div>
    </div>
  );
}
