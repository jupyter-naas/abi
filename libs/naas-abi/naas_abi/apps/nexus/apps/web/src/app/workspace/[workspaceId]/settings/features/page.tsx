'use client';

/**
 * Settings › Access › Features: which features a policy of the workspace allows, "<W> access" (its
 * offer) by default, laid out as Settings › Users. The policy edited is picked in the Settings column and kept in the URL (`?policy=`).
 * Files are Settings › Files.
 */
import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Loading } from '@/components/ui/spinner';
import { FeatureAccess } from './feature-access';
// The choices and notes of a row.
import '../general/general.css';
// The table of Settings › Users: columns that sort and filter.
import '@/app/organizations/[orgId]/settings/users/users.css';

function Features() {
  const workspaceId = useParams().workspaceId as string;
  const policy = useSearchParams().get('policy');
  return (
    <FeatureAccess
      // The policy is picked in the Settings column (`?policy=`): another one opens the page afresh.
      key={`${workspaceId}:${policy ?? ''}`}
      workspaceId={workspaceId}
      policyPicker={false}
      initialPolicy={policy}
    />
  );
}

export default function FeaturesSettingsPage() {
  return (
    <Suspense fallback={<Loading label="Loading features…" />}>
      <Features />
    </Suspense>
  );
}
