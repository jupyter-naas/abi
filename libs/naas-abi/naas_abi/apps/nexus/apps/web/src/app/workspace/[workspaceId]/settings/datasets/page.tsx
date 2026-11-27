'use client';

/**
 * Settings › Datasets: the dataset namespaces the workspace uses, in its offer "<W> access"
 * (`OfferDatasetsDeny`), laid out as Settings › Users.
 */
import { useParams } from 'next/navigation';
import { DatasetsOffer } from './datasets';
// The notes of a row.
import '../general/general.css';
// The table of Settings › Users: columns that sort and filter.
import '@/app/organizations/[orgId]/settings/users/users.css';

export default function DatasetsSettingsPage() {
  const workspaceId = useParams().workspaceId as string;
  return <DatasetsOffer key={workspaceId} target={workspaceId} />;
}
