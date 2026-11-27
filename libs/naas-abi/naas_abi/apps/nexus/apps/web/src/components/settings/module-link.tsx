'use client';

import Link from 'next/link';
import { cn } from '@/lib/utils';
import { moduleRowHref } from '@/app/workspace/[workspaceId]/settings/modules/modules-model';

/**
 * A module named on a page under Features (Agents, Apps, Workflows): a link to its row in Access ›
 * Modules, where the workspace offers it whole or item by item. A click on it does not open the
 * row it sits in.
 */
export function ModuleLink({ workspaceId, module, className }: { workspaceId: string; module: string; className?: string }) {
  if (!module) return null;
  return (
    <Link
      href={moduleRowHref(workspaceId, module)}
      data-module-link=""
      title={`What this workspace offers of ${module}: Access › Modules`}
      className={cn('hover:text-primary hover:underline', className)}
      onClick={(event) => event.stopPropagation()}
    >
      {module}
    </Link>
  );
}
