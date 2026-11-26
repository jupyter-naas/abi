'use client';

/** Settings › Access › Modules: what the workspace offers of each module (`WorkspaceModules`). */
import { useParams } from 'next/navigation';
import { WorkspaceModules } from './modules';

export default function ModulesSettingsPage() {
  const workspaceId = useParams().workspaceId as string;
  return <WorkspaceModules workspaceId={workspaceId} />;
}
