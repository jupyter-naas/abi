'use client';

import { useParams } from 'next/navigation';
import { ModelsPanel } from '@/components/settings/models-panel';
import { WorkspaceOfferPart } from '@/components/settings/workspace-offer-part';

/** Settings › Models: the models of the platform, and those this workspace's chats use (its offer). */
export default function ModelsPage() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  return (
    <div className="space-y-6">
      <ModelsPanel />
      {workspaceId && (
        <WorkspaceOfferPart
          workspaceId={workspaceId}
          parts={['models']}
          description="The chat models used here, and the default one an agent built on another model runs on."
        />
      )}
    </div>
  );
}
