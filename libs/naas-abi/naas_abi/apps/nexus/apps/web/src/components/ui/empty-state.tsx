import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * What a list, table or pane shows when it has nothing: an icon, one line saying so, an
 * optional explanation and the action that fills it. `framed` draws the dashed outline
 * a page uses; inside a pane or a table, leave it off.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  framed = false,
  className,
}: {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  framed?: boolean;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col items-center justify-center gap-2 px-6 py-12 text-center',
        framed && 'border border-dashed border-border',
        className
      )}
    >
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
