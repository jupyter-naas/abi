'use client';

import { Lock } from 'lucide-react';
import { SettingsEmpty } from '@/components/settings/settings-ui';

/**
 * Settings of a workspace or an organization IAM gives the caller no section of, opened by
 * URL: nothing of them is shown. The menus and the dock offer no link here on the same rule.
 */
export function SettingsNoAccess({ of }: { of: 'workspace' | 'organization' }) {
  return (
    <SettingsEmpty
      icon={<Lock size={40} className="opacity-40" />}
      title="You have no access to these settings"
      description={`Your role and policies give you nothing to manage in this ${of}'s settings. Its owners and admins manage them.`}
    />
  );
}
