import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * A page's (or a full-width pane's) title line: optional leading element (back button,
 * avatar), title, count badge, description, then actions pinned top-right.
 */
export function PageHeader({
  title,
  badge,
  description,
  actions,
  leading,
  className,
}: {
  title: ReactNode;
  /** Shown next to the title, e.g. "9 enabled". */
  badge?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  leading?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="flex min-w-0 flex-1 items-start gap-3">
        {leading}
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <h2 className="truncate text-lg font-semibold text-foreground">{title}</h2>
            {badge !== undefined && badge !== null ? (
              <span className="inline-flex shrink-0 items-center bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {badge}
              </span>
            ) : null}
          </div>
          {description ? <p className="mt-0.5 text-sm text-muted-foreground">{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="flex shrink-0 items-center justify-end gap-2">{actions}</div> : null}
    </div>
  );
}
