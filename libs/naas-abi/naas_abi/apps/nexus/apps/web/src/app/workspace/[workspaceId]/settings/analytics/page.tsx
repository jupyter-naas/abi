'use client';

import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { useParams } from 'next/navigation';
import { AnalyticsSection } from '@/components/analytics/analytics-section';
import { SettingsPageHeader } from '@/components/settings/settings-ui';

/** Workspace Settings › Analytics: the workspace's members, in this workspace. */
export default function WorkspaceAnalyticsPage() {
  const workspaceId = useParams().workspaceId as string;
  return (
    <div className="space-y-6">
      <SettingsPageHeader title="Analytics" description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/analytics']} />
      {workspaceId ? <AnalyticsSection key={workspaceId} scope={{ kind: 'workspace', workspaceId }} /> : null}
    </div>
  );
}
