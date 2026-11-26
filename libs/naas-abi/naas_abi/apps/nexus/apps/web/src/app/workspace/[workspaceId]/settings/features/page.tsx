'use client';

/**
 * Settings › Features: whether the workspace offers each feature (its offer's Features part), apart
 * from General's identity and look. Files are Settings › Files.
 */
import { useParams } from 'next/navigation';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { FeatureAccess } from './feature-access';
import '../general/general.css';

export default function FeaturesSettingsPage() {
  const workspaceId = useParams().workspaceId as string;
  return (
    <div className="workspace-general space-y-6">
      <AccountPageHeader
        title="Features"
        subtitle="Which features this workspace offers to its people, within each one's level."
      />
      <FeatureAccess workspaceId={workspaceId} />
    </div>
  );
}
