'use client';

/**
 * Settings › Access › Modules: what a policy of the workspace allows of each module, "<W> access"
 * (its offer) by default (`WorkspaceModules`). The policy edited is picked in the Settings column and kept in the URL (`?policy=`).
 */
import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { Loading } from '@/components/ui/spinner';
import { WorkspaceModules } from './modules';

function Modules() {
  const workspaceId = useParams().workspaceId as string;
  const search = useSearchParams();
  const policy = search.get('policy');
  return (
    <WorkspaceModules
      // The policy is picked in the Settings column (`?policy=`): another one opens the page afresh.
      key={`${workspaceId}:${policy ?? ''}`}
      workspaceId={workspaceId}
      policyPicker={false}
      initialPolicy={policy}
      initialSearch={search.get('module')}
    />
  );
}

export default function ModulesSettingsPage() {
  return (
    <Suspense fallback={<Loading label="Loading modules…" />}>
      <Modules />
    </Suspense>
  );
}
