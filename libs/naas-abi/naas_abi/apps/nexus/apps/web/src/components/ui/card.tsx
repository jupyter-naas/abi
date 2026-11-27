import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** A titled block of a page: heading, description and actions on top, then the body. */
export function Card({
  title,
  description,
  actions,
  children,
  flush = false,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  /** No body padding: a table or a list that runs edge to edge. */
  flush?: boolean;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn('border border-border bg-card', className)}>
      {title || actions ? (
        <div className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
          <div className="min-w-0">
            {title ? <h3 className="text-sm font-semibold text-foreground">{title}</h3> : null}
            {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className={cn(!flush && 'p-4', bodyClassName)}>{children}</div>
    </section>
  );
}
