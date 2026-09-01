'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ChevronRight,
  FileCode2,
  FileJson,
  FileText,
  Folder,
  Image as ImageIcon,
  LayoutTemplate,
  Presentation,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SlidesExplorerIcon, SlidesExplorerNode } from '@/lib/slides-explorer';

function NodeIcon({ icon, accent }: { icon: SlidesExplorerIcon; accent?: string }) {
  if (icon === 'html') return <FileCode2 size={11} className="flex-shrink-0 text-muted-foreground" />;
  if (icon === 'json') return <FileJson size={11} className="flex-shrink-0 text-muted-foreground" />;
  if (icon === 'md') return <FileText size={11} className="flex-shrink-0 text-muted-foreground" />;
  if (icon === 'image') return <ImageIcon size={11} className="flex-shrink-0 text-muted-foreground" />;
  if (icon === 'presentation') {
    return <Presentation size={11} className="flex-shrink-0 text-muted-foreground" />;
  }
  if (icon === 'template') {
    return (
      <span className="flex flex-shrink-0 items-center gap-1">
        <span
          className="h-2 w-2 rounded-sm border border-border/70"
          style={accent ? { background: accent } : undefined}
          aria-hidden
        />
        <LayoutTemplate size={11} className="text-muted-foreground" />
      </span>
    );
  }
  return <Folder size={11} className="flex-shrink-0 text-muted-foreground" />;
}

export function SlidesExplorerTree({
  nodes,
  expandedIds,
  selectedId,
  renamingId,
  onToggle,
  onActivate,
  onStartRename,
  onCommitRename,
  onCancelRename,
}: {
  nodes: SlidesExplorerNode[];
  expandedIds: string[];
  selectedId: string | null;
  renamingId: string | null;
  onToggle: (id: string) => void;
  onActivate: (node: SlidesExplorerNode) => void;
  onStartRename: (node: SlidesExplorerNode) => void;
  onCommitRename: (node: SlidesExplorerNode, nextName: string) => void;
  onCancelRename: () => void;
}) {
  return (
    <div role="tree" className="space-y-0.5">
      {nodes.map((node) => (
        <ExplorerRow
          key={node.id}
          node={node}
          depth={0}
          expandedIds={expandedIds}
          selectedId={selectedId}
          renamingId={renamingId}
          onToggle={onToggle}
          onActivate={onActivate}
          onStartRename={onStartRename}
          onCommitRename={onCommitRename}
          onCancelRename={onCancelRename}
        />
      ))}
    </div>
  );
}

function RenameField({
  name,
  onCommit,
  onCancel,
}: {
  name: string;
  onCommit: (next: string) => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(name);

  useEffect(() => {
    ref.current?.focus();
    ref.current?.select();
  }, []);

  return (
    <input
      ref={ref}
      aria-label="Rename presentation"
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => onCommit(value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          onCommit(value);
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          onCancel();
        }
      }}
      className="min-w-0 flex-1 rounded border border-workspace-accent bg-background px-1 py-0.5 text-xs text-foreground outline-none"
    />
  );
}

function ExplorerRow({
  node,
  depth,
  expandedIds,
  selectedId,
  renamingId,
  onToggle,
  onActivate,
  onStartRename,
  onCommitRename,
  onCancelRename,
}: {
  node: SlidesExplorerNode;
  depth: number;
  expandedIds: string[];
  selectedId: string | null;
  renamingId: string | null;
  onToggle: (id: string) => void;
  onActivate: (node: SlidesExplorerNode) => void;
  onStartRename: (node: SlidesExplorerNode) => void;
  onCommitRename: (node: SlidesExplorerNode, nextName: string) => void;
  onCancelRename: () => void;
}) {
  const isFolder = node.kind === 'folder';
  const expanded = isFolder && expandedIds.includes(node.id);
  const selected = selectedId === node.id;
  const renaming = renamingId === node.id;
  const children = node.children ?? [];
  const pad = 8 + depth * 12;

  return (
    <div>
      <div className="flex items-center gap-0.5" style={{ paddingLeft: pad }}>
        {isFolder ? (
          <button
            type="button"
            role="treeitem"
            aria-expanded={expanded}
            aria-label={`${expanded ? 'Collapse' : 'Expand'} ${node.name}`}
            onClick={() => onToggle(node.id)}
            className="rounded p-1 text-muted-foreground hover:bg-workspace-accent-10 hover:text-foreground"
          >
            <ChevronRight
              size={11}
              className={cn('transition-transform', expanded && 'rotate-90')}
            />
          </button>
        ) : (
          <span className="w-5 flex-shrink-0" />
        )}
        {renaming ? (
          <div className="flex min-w-0 flex-1 items-center gap-2 px-1.5 py-0.5">
            <NodeIcon icon={node.icon} accent={node.accent} />
            <RenameField
              name={node.name}
              onCommit={(next) => onCommitRename(node, next)}
              onCancel={onCancelRename}
            />
          </div>
        ) : (
          <button
            type="button"
            role="treeitem"
            aria-selected={selected}
            onClick={() => onActivate(node)}
            onDoubleClick={(event) => {
              if (!node.renamable) return;
              event.preventDefault();
              event.stopPropagation();
              onStartRename(node);
            }}
            onContextMenu={(event) => {
              if (!node.renamable) return;
              event.preventDefault();
              onStartRename(node);
            }}
            onKeyDown={(event) => {
              if (node.renamable && event.key === 'F2') {
                event.preventDefault();
                onStartRename(node);
              }
            }}
            title={
              node.renamable
                ? `${node.name} (F2 or right-click to rename)`
                : node.hint
                  ? `${node.name} (${node.hint})`
                  : node.name
            }
            className={cn(
              'flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-1 text-xs transition-colors hover:bg-workspace-accent-10',
              selected
                ? 'bg-workspace-accent-10 font-medium text-workspace-accent'
                : 'text-foreground',
            )}
          >
            <NodeIcon icon={node.icon} accent={node.accent} />
            <span className="truncate">{node.name}</span>
            {node.hint ? (
              <span className="ml-auto truncate text-[10px] text-muted-foreground">{node.hint}</span>
            ) : null}
          </button>
        )}
      </div>
      {isFolder && expanded ? (
        <div>
          {children.length === 0 && node.emptyLabel ? (
            <p
              className="py-0.5 text-[10px] text-muted-foreground"
              style={{ paddingLeft: pad + 22 }}
            >
              {node.emptyLabel}
            </p>
          ) : (
            children.map((child) => (
              <ExplorerRow
                key={child.id}
                node={child}
                depth={depth + 1}
                expandedIds={expandedIds}
                selectedId={selectedId}
                renamingId={renamingId}
                onToggle={onToggle}
                onActivate={onActivate}
                onStartRename={onStartRename}
                onCommitRename={onCommitRename}
                onCancelRename={onCancelRename}
              />
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
