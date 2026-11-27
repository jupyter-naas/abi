'use client';

/** Settings › Files: every kind of files the people of the workspace open (``WorkspaceFiles``). */
import { useParams } from 'next/navigation';
import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { WorkspaceFiles } from './workspace-files';
import '../general/general.css';

export default function FilesSettingsPage() {
  const workspaceId = useParams().workspaceId as string;
  return (
    <div className="workspace-general space-y-6">
      {/* The header of every page under Features (`SettingsPageHeader`), drawn by `WorkspaceFiles`. */}
      <WorkspaceFiles
        workspaceId={workspaceId}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/files']}
      />
    </div>
  );
}
