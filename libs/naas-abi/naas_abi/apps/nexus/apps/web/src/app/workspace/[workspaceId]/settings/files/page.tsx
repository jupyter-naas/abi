'use client';

/** Settings › Files: every kind of files the people of the workspace open (``WorkspaceFiles``). */
import { useParams } from 'next/navigation';
import { AccountPageHeader } from '@/app/account/components/account-page-header';
import { WorkspaceFiles } from './workspace-files';
import '../general/general.css';

export default function FilesSettingsPage() {
  const workspaceId = useParams().workspaceId as string;
  return (
    <div className="workspace-general space-y-6">
      <AccountPageHeader
        title="Files"
        subtitle="Workspace, Organization, Platform and System Files: what the people of this workspace open, and change."
      />
      <WorkspaceFiles workspaceId={workspaceId} />
    </div>
  );
}
