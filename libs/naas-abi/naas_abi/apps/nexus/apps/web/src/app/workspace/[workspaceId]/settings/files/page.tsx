'use client';

/** Settings › Files: every kind of files the people of the workspace open (``WorkspaceFiles``), on
 *  "<W> access" or the policy picked in the Settings column (`?policy=`). */
import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { policyOfSearch } from '@/components/settings/settings-policy';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { WorkspaceFiles } from './workspace-files';
import '../general/general.css';

function Files() {
  const workspaceId = useParams().workspaceId as string;
  const policy = policyOfSearch(useSearchParams());
  return (
    <div className="workspace-general space-y-6">
      {/* The header of every page under Features (`SettingsPageHeader`), drawn by `WorkspaceFiles`. */}
      <WorkspaceFiles
        key={`${workspaceId}:${policy ?? ''}`}
        workspaceId={workspaceId}
        policyId={policy}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/files']}
      />
    </div>
  );
}

export default function FilesSettingsPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading files…" />}>
      <Files />
    </Suspense>
  );
}
