'use client';
import dynamic from 'next/dynamic';
import { useParams, useSearchParams } from 'next/navigation';
import { GraphObjectPage } from '@/components/graph/graph-object-page';
// Preserve bulk browsing for legacy links without an individual selection.
const IndividualsBrowser = dynamic(() => import('@/components/graph/individuals-browser'), {ssr: false});
export default function IndividualsPage() {
  const {workspaceId} = useParams<{workspaceId: string}>();
  const query = useSearchParams();
  const selected = query.get('selected');
  return selected ? <GraphObjectPage workspaceId={workspaceId} graphUri={query.get('graph') || ''} instanceUri={selected} /> : <IndividualsBrowser />;
}
