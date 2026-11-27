'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { SettingsLoading, SettingsPageHeader } from '@/components/settings/settings-ui';
import { policyOfSearch } from '@/components/settings/settings-policy';
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
 * Settings › Models: the chat models this workspace's chats use, its part of the offer (or what
 * the policy picked in the Settings column grants, `?policy=`). The platform's catalog of models
 * is Platform › Models, linked from here.
 */
export default function ModelsPage() {
  return (
    <Suspense fallback={<SettingsLoading label="Loading models…" />}>
      <Models />
    </Suspense>
  );
}

function Models() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const policy = policyOfSearch(useSearchParams());
  const [part, setPart] = useState<ModelsPart | undefined>(undefined);

  const load = useCallback(async () => {
    if (!workspaceId) return;
    try {
      setPart((await OFFER_API.read(workspaceId, policy)).models);
    } catch {
      setPart(undefined);
    }
  }, [workspaceId, policy]);

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
        <WorkspaceOfferPart
          key={policy ?? ''}
          workspaceId={workspaceId}
          parts={['models']}
          policyId={policy}
          onChanged={() => void load()}
        />
      )}
    </div>
  );
}
