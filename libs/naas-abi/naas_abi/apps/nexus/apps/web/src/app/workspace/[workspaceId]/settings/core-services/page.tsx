'use client';

/**
 * Settings › Access › Services: how far people go with each core service in the workspace, for a
 * policy picked in the header ("<W> access" by default, `?policy=`). `CoreServices`.
 */
import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { CoreServices } from './core-services';
// The level choices (General's CSS).
import '../general/general.css';

function Services() {
  const workspaceId = useParams().workspaceId as string;
  const policy = useSearchParams().get('policy');
  return (
    <CoreServices
      // The policy is picked in the Settings column (`?policy=`): another one opens the page afresh.
      key={`${workspaceId}:${policy ?? ''}`}
      workspaceId={workspaceId}
      policyPicker={false}
      initialPolicy={policy}
    />
  );
}

export default function CoreServicesSettingsPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading services…" />}>
      <Services />
    </Suspense>
  );
}
