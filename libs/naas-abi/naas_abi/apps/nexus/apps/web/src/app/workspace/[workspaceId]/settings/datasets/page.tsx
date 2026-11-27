'use client';

/**
 * Settings › Datasets: the dataset namespaces the workspace uses, in its offer "<W> access"
 * (`OfferDatasetsDeny`), or those another policy picked in the Settings column closes for its
 * holders (`?policy=`), laid out as Settings › Users.
 */
import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Loading } from '@/components/ui/spinner';
import { policyOfSearch } from '@/components/settings/settings-policy';
import { DatasetsOffer } from './datasets';
// The notes of a row.
import '../general/general.css';
// The table of Settings › Users: columns that sort and filter.
import '@/app/organizations/[orgId]/settings/users/users.css';

function Datasets() {
  const workspaceId = useParams().workspaceId as string;
  const policy = policyOfSearch(useSearchParams());
  return <DatasetsOffer key={`${workspaceId}:${policy ?? ''}`} target={workspaceId} policyId={policy} />;
}

export default function DatasetsSettingsPage() {
  return (
    <Suspense fallback={<Loading label="Loading datasets…" />}>
      <Datasets />
    </Suspense>
  );
}
