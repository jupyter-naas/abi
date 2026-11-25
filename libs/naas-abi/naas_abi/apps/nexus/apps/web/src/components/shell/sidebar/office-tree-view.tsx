'use client';

import { useState } from 'react';
import Link from 'next/link';
import { File, FileCode2, Folder, Image as ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TreeRow, TreeTwisty, treeRowClass } from '@/components/ui/tree-row';
import type { OfficeKind } from '@/components/office/office-kinds';
import { OfficeProjectMenu } from '@/components/office/office-project-menu';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import {
  isOfficeGalleryPath,
  type OfficeTreeFileNode,
  type OfficeTreeItemNode,
} from './office-tree';

/**
 * The Documents, Sheets and Slides sidebar tree.
 *
 * Nested disclosure lists rather than `role="tree"`: every row here is already
 * a real link or button, so Tab reaches all of them and Enter activates them.
 * Claiming `role="tree"` would promise one tab stop plus roving focus, which
 * this does not implement, and a false role is worse than no role.
 *
 * Items are anchors, so cmd-click and middle-click open one in a new tab while a
 * plain click stays inside the workspace shell.
 */

type TreeKind = Pick<
  OfficeKind,
  'id' | 'testIdPrefix' | 'fileName' | 'itemTestId' | 'icon' | 'treeRootLabel' | 'allRowLabel' | 'emptyLabel'
>;

/** Line for an empty list or a tree still loading: same density as a row, nothing to click. */
const NOTE_CLASS = 'px-2 py-1 text-xs leading-[18px] text-muted-foreground';

function toggleLabel(expanded: boolean, name: string): string {
  return `${expanded ? 'Collapse' : 'Expand'} ${name}`;
}

function FileIcon({ node, fileName }: { node: OfficeTreeFileNode; fileName: string }) {
  const Icon =
    node.type === 'dir'
      ? Folder
      : node.name === fileName
        ? FileCode2
        : /\.(png|jpe?g|gif|svg|webp)$/i.test(node.name)
          ? ImageIcon
          : File;
  return <Icon size={11} className="flex-shrink-0 text-muted-foreground" />;
}

type RowActions = {
  renamingSlug?: string | null;
  onStartRename?: (slug: string) => void;
  onRename?: (slug: string, title: string) => void;
  onCancelRename?: () => void;
  onArchive?: (slug: string) => void;
};

function ItemRow({
  kind,
  item,
  currentPath,
  expanded,
  onToggleItem,
  onOpenItem,
  actions,
}: {
  kind: TreeKind;
  item: OfficeTreeItemNode;
  currentPath?: string;
  expanded: boolean;
  onToggleItem: (slug: string) => void;
  onOpenItem: (item: OfficeTreeItemNode) => void;
  actions: RowActions;
}) {
  const { onStartRename, onRename, onCancelRename, onArchive } = actions;
  const renaming = actions.renamingSlug === item.slug;
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(item.label);
  const canAct = Boolean(onStartRename && onRename && onArchive);

  const submitRename = () => {
    const next = editValue.trim();
    if (next && next !== item.label) onRename?.(item.slug, next);
    onCancelRename?.();
  };

  return (
    <TreeRow
      twisty={
        <TreeTwisty
          expanded={expanded}
          label={toggleLabel(expanded, item.label)}
          onToggle={() => onToggleItem(item.slug)}
        />
      }
      menuOpen={showMenu}
      onContextMenu={(event) => {
        if (!canAct || renaming) return;
        event.preventDefault();
        setShowMenu(true);
      }}
      actions={
        canAct && !renaming ? (
          <OfficeProjectMenu
            kind={kind}
            open={showMenu}
            onOpenChange={setShowMenu}
            onRename={() => {
              setEditValue(item.label);
              onStartRename?.(item.slug);
            }}
            onArchive={() => onArchive?.(item.slug)}
          />
        ) : null
      }
    >
      {renaming ? (
        <div className="chat-rename-row min-w-0 flex-1">
          <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
          <input
            type="text"
            value={editValue}
            onChange={(event) => setEditValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submitRename();
              else if (event.key === 'Escape') onCancelRename?.();
            }}
            onBlur={submitRename}
            autoFocus
            className="chat-rename-input"
            data-testid={`${kind.testIdPrefix}-rename-input`}
          />
        </div>
      ) : (
        <Link
          href={item.href}
          onClick={() => onOpenItem(item)}
          title={item.label}
          aria-current={item.href === currentPath ? 'page' : undefined}
          data-testid={kind.itemTestId}
          data-slug={item.slug}
          className={treeRowClass({ active: item.active })}
        >
          <Folder size={11} className="flex-shrink-0 text-muted-foreground" />
          <span className="truncate">{item.label}</span>
        </Link>
      )}
    </TreeRow>
  );
}

function FileRows({
  kind,
  nodes,
  itemHref,
  onOpenItem,
  expandedDirs,
  onToggleDir,
}: {
  kind: TreeKind;
  nodes: OfficeTreeFileNode[];
  itemHref: string;
  onOpenItem: () => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
}) {
  return (
    <ul className="ml-3 list-none space-y-0.5 p-0">
      {nodes.map((node) => {
        const expandable = node.type === 'dir' && node.children.length > 0;
        const expanded = expandable && expandedDirs.includes(node.path);
        // The item's own HTML file is what the pane edits, so it routes to the item.
        // project.json and assets have no viewer, so they stay inert instead of
        // pretending to be clickable.
        const isItemFile = node.type === 'file' && node.name === kind.fileName;
        const label = (
          <>
            <FileIcon node={node} fileName={kind.fileName} />
            <span className="truncate">{node.name}</span>
          </>
        );
        return (
          <li key={node.path || node.name}>
            <TreeRow
              twisty={
                <TreeTwisty
                  expanded={expandable ? expanded : undefined}
                  label={toggleLabel(expanded, node.name)}
                  onToggle={() => onToggleDir(node.path)}
                />
              }
            >
              {isItemFile ? (
                <Link
                  href={itemHref}
                  onClick={onOpenItem}
                  title={node.path}
                  data-testid={`${kind.id}-tree-file`}
                  className={cn(treeRowClass(), node.open && 'text-workspace-accent')}
                >
                  {label}
                </Link>
              ) : (
                <span
                  title={node.path}
                  data-testid={`${kind.id}-tree-file`}
                  className={treeRowClass({ muted: true })}
                >
                  {label}
                </span>
              )}
            </TreeRow>
            {expanded ? (
              <FileRows
                kind={kind}
                nodes={node.children}
                itemHref={itemHref}
                onOpenItem={onOpenItem}
                expandedDirs={expandedDirs}
                onToggleDir={onToggleDir}
              />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

export type OfficeTreeViewProps = RowActions & {
  kind: TreeKind;
  items: OfficeTreeItemNode[];
  /** Root row links to the kind's index. */
  rootHref: string;
  /**
   * Route the sidebar is on. An item keeps its selection styling as the last
   * one opened, but only claims to be the current page when the route is
   * really on it.
   */
  currentPath?: string;
  rootExpanded: boolean;
  onToggleRoot: () => void;
  expandedItems: string[];
  onToggleItem: (slug: string) => void;
  expandedDirs: string[];
  onToggleDir: (path: string) => void;
  onOpenItem: (item: OfficeTreeItemNode) => void;
  emptyLabel?: string;
  /** Archived list: item rows only, no second root. */
  hideRoot?: boolean;
};

export function OfficeTreeView({
  kind,
  items,
  rootHref,
  currentPath,
  rootExpanded,
  onToggleRoot,
  expandedItems,
  onToggleItem,
  expandedDirs,
  onToggleDir,
  onOpenItem,
  emptyLabel = kind.emptyLabel,
  hideRoot = false,
  ...actions
}: OfficeTreeViewProps) {
  const list =
    items.length === 0 ? (
      <li>
        <p className={NOTE_CLASS}>{emptyLabel}</p>
      </li>
    ) : (
      items.map((item) => {
        const expanded = expandedItems.includes(item.slug);
        return (
          <li key={item.slug}>
            <ItemRow
              kind={kind}
              item={item}
              currentPath={currentPath}
              expanded={expanded}
              onToggleItem={onToggleItem}
              onOpenItem={onOpenItem}
              actions={actions}
            />
            {expanded ? (
              item.filesLoaded ? (
                <FileRows
                  kind={kind}
                  nodes={item.files}
                  itemHref={item.href}
                  onOpenItem={() => onOpenItem(item)}
                  expandedDirs={expandedDirs}
                  onToggleDir={onToggleDir}
                />
              ) : (
                <p className={cn('ml-3 pl-6', NOTE_CLASS)}>Loading</p>
              )
            ) : null}
          </li>
        );
      })
    );

  if (hideRoot) {
    return (
      <ul className="list-none space-y-0.5 p-0" data-testid={`${kind.id}-tree-archived`}>
        {list}
      </ul>
    );
  }

  const onGallery = isOfficeGalleryPath(currentPath, rootHref);
  const AllIcon = kind.icon;

  return (
    <ul className="list-none space-y-0.5 p-0" data-testid={`${kind.id}-tree`}>
      <li>
        <Link
          href={rootHref}
          data-testid={`${kind.id}-tree-all`}
          aria-current={onGallery ? 'page' : undefined}
          className={cn(
            treeRowClass(),
            onGallery ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground',
          )}
        >
          <AllIcon size={12} className="flex-shrink-0 text-muted-foreground" />
          <span className="truncate">{kind.allRowLabel}</span>
        </Link>
      </li>
      <li>
        <TreeRow
          twisty={
            <TreeTwisty
              expanded={rootExpanded}
              label={toggleLabel(rootExpanded, kind.treeRootLabel)}
              onToggle={onToggleRoot}
            />
          }
        >
          <Link href={rootHref} data-testid={`${kind.id}-tree-root`} className={treeRowClass()}>
            <Folder size={12} className="flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{kind.treeRootLabel}</span>
          </Link>
        </TreeRow>

        {rootExpanded ? <ul className="ml-3 list-none space-y-0.5 p-0">{list}</ul> : null}
      </li>
    </ul>
  );
}
