'use client';

import type { ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * One row of a sidebar list or tree (12/18 density): an optional disclosure triangle (or
 * its spacer, so labels align), an icon, the label, then actions that show on hover. The
 * row itself is whatever `children` is: a link, a button, an inline rename field.
 */
export function TreeTwisty({
  expanded,
  label,
  onToggle,
}: {
  /** `undefined` draws the spacer: a row without children, aligned with its siblings. */
  expanded?: boolean;
  label?: string;
  onToggle?: () => void;
}) {
  if (expanded === undefined) return <span className="h-5 w-4 shrink-0" aria-hidden />;
  return (
    <button
      type="button"
      aria-expanded={expanded}
      aria-label={label}
      onClick={onToggle}
      className="flex h-5 w-4 shrink-0 items-center justify-center rounded text-muted-foreground hover:text-foreground"
    >
      <ChevronRight size={11} className={cn('transition-transform', expanded && 'rotate-90')} />
    </button>
  );
}

/** Classes for the row's main element (link or button), so every tree reads alike. */
export function treeRowClass({
  active,
  muted,
  inert,
}: {
  active?: boolean;
  muted?: boolean;
  /** A row that does nothing when clicked: no hover, so it does not pretend to be a link. */
  inert?: boolean;
} = {}) {
  return cn(
    'flex min-w-0 flex-1 items-center gap-1 rounded-md px-2 py-1 text-xs leading-[18px] no-underline transition-colors',
    !inert && 'hover:bg-workspace-accent-10',
    active ? 'bg-workspace-accent-15 font-medium text-workspace-accent' : muted || inert ? 'text-muted-foreground' : 'text-foreground'
  );
}

export function TreeRow({
  twisty,
  actions,
  menuOpen,
  onContextMenu,
  children,
  className,
}: {
  twisty?: ReactNode;
  /** Shown on hover or focus, while the row's menu is open, and always on small (touch) screens. */
  actions?: ReactNode;
  menuOpen?: boolean;
  onContextMenu?: (event: React.MouseEvent) => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn('group/tree-row flex min-w-0 items-center', className)}
      data-menu-open={menuOpen || undefined}
      onContextMenu={onContextMenu}
    >
      {twisty}
      {children}
      {actions ? (
        <div className="flex shrink-0 items-center opacity-0 transition-opacity focus-within:opacity-100 group-hover/tree-row:opacity-100 group-data-[menu-open]/tree-row:opacity-100 max-md:opacity-100">
          {actions}
        </div>
      ) : null}
    </div>
  );
}
