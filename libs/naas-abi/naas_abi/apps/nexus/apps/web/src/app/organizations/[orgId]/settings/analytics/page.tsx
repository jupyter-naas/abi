'use client';

import { useParams } from 'next/navigation';
import { AnalyticsSection } from '@/components/analytics/analytics-section';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';

/** Organization Settings › Analytics: the organization's members, across its workspaces. */
export default function OrganizationAnalyticsPage() {
  const orgId = useParams().orgId as string;
  return (
    <div className="space-y-6">
      <OrgSettingsPageHeader
        title="Analytics"
        subtitle="How the organization's members use Nexus, across its workspaces"
      />
      {orgId ? <AnalyticsSection key={orgId} scope={{ kind: 'organization', orgId }} /> : null}
    </div>
  );
}
