'use client';

import { useParams } from 'next/navigation';
import { InstanceBack } from '@/components/settings/instance-form';
import { ModelsPanel } from '@/components/settings/models-panel';

/**
 * Settings › Models › Model catalog: every model the platform's AI modules bring, each opening its
 * page (display properties, source identity). Models lists what this workspace's chats use; this
 * is what they may be picked from.
 */
export default function ModelCatalogPage() {
  const workspaceId = useParams()?.workspaceId as string;
  return (
    <div className="space-y-6" data-model-catalog="">
      <InstanceBack href={`/workspace/${workspaceId}/settings/models`} label="Models" />
      <ModelsPanel />
    </div>
  );
}
