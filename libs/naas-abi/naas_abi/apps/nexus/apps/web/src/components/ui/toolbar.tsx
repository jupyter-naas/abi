import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * The bar above a pane's content: search and filters on the left, actions on the right.
 * Put the items that belong together in a `ToolbarGroup`, and a `ToolbarSeparator`
 * between groups. Use `Button size="icon"` (or `sm`) for its buttons.
 */
export function Toolbar({
  children,
  end,
  label,
  className,
}: {
  children?: ReactNode;
  /** Pushed to the right edge (the pane's actions). */
  end?: ReactNode;
  /** Accessible name, e.g. "Files toolbar". */
  label: string;
  className?: string;
}) {
  return (
    <div
      role="toolbar"
      aria-label={label}
      className={cn('flex min-h-10 min-w-0 items-center gap-2 border-b border-border px-3 py-1.5', className)}
    >
      {children}
      {end ? <div className="ml-auto flex shrink-0 items-center gap-1">{end}</div> : null}
    </div>
  );
}

export function ToolbarGroup({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('flex min-w-0 items-center gap-1', className)}>{children}</div>;
}

export function ToolbarSeparator() {
  return <span role="separator" aria-orientation="vertical" className="mx-1 h-5 w-px shrink-0 bg-border" />;
}
