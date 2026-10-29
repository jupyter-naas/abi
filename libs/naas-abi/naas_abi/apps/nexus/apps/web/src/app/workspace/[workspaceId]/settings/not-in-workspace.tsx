'use client';

import { Blocks } from 'lucide-react';
import { SettingsEmpty } from '@/components/settings/settings-ui';

/**
 * A settings page of something the caller may not use in the workspace (a feature they do not
 * hold, or no agent, app, workflow or pipeline of that kind they may use): nothing to manage.
 */
export function NotInWorkspace({ label }: { label: string }) {
  return (
    <SettingsEmpty
      icon={<Blocks size={40} className="opacity-40" />}
      title={`${label} is not available to you in this workspace`}
      description="Policies decide what you may use here, on Roles & permissions."
    />
  );
}
