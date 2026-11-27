'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { WorkspaceOfferPart } from '@/components/settings/workspace-offer-part';
import { PLATFORM_MODELS_PATH } from '@/app/settings/lib/nav';
import { createOfferApi, type ModelsPart } from '@/lib/access-model/workspace-offer';
// The secondary button of Settings › Users.
import '@/app/organizations/[orgId]/settings/users/users.css';

const OFFER_API = createOfferApi();

/** "Every model", or how many models the workspace uses. */
function modelsBadge(part: ModelsPart | undefined): string | undefined {
  if (!part) return undefined;
  if (part.every) return 'Every model';
  return `${part.offered.length} model${part.offered.length === 1 ? '' : 's'}`;
}

/**
 * Settings › Models: the chat models this workspace's chats use, its part of the offer. The
 * platform's catalog of models is Platform › Models, linked from here.
 */
export default function ModelsPage() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const [part, setPart] = useState<ModelsPart | undefined>(undefined);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    try {
      setPart((await OFFER_API.read(workspaceId)).models);
    } catch {
      setPart(undefined);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Models"
        badge={modelsBadge(part)}
        description={WORKSPACE_PAGE_DESCRIPTIONS['/settings/models']}
        actions={
          <Link
            href={PLATFORM_MODELS_PATH}
            className="org-settings-users-secondary-button"
            data-action="platform-models"
            title="Every model of the platform: Platform › Models"
          >
            Platform models
          </Link>
        }
      />
      {workspaceId && (
        <WorkspaceOfferPart workspaceId={workspaceId} parts={['models']} onChanged={() => void load()} />
      )}
    </div>
  );
}
