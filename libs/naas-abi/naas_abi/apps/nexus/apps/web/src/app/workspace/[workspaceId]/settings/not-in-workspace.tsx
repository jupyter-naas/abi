'use client';

import { Blocks } from 'lucide-react';
import { EmptyState } from '@/components/ui/empty-state';

/**
 * A settings page of something the caller may not use in the workspace (a feature they do not
 * hold, or no agent, app, workflow or pipeline of that kind they may use): nothing to manage.
 */
export function NotInWorkspace({ label }: { label: string }) {
  return (
    <EmptyState framed
      icon={<Blocks size={40} className="opacity-40" />}
      title={`${label} is not available to you in this workspace`}
      description="Policies decide what you may use here, in Access › Policies."
    />
  );
}
