'use client';

/**
 * Settings › Features: whether the workspace offers each feature (its offer's Features part), laid
 * out as Settings › Users. Files are Settings › Files.
 */
import { useParams } from 'next/navigation';
import { FeatureAccess } from './feature-access';
// The choices and notes of a row.
import '../general/general.css';
// The table of Settings › Users: columns that sort and filter.
import '@/app/organizations/[orgId]/settings/users/users.css';

export default function FeaturesSettingsPage() {
  const workspaceId = useParams().workspaceId as string;
  return <FeatureAccess workspaceId={workspaceId} />;
}
