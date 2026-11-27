'use client';

import Link from 'next/link';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { Loading } from '@/components/ui/spinner';
import { policyOfSearch } from '@/components/settings/settings-policy';
import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { WorkspaceOfferPart } from '@/components/settings/workspace-offer-part';
import { usePolicyHref } from '@/components/settings/use-policy-href';
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
 * the policy picked in the Settings column grants, `?policy=`). The models they are picked from
 * are the Model catalog (`models/catalog`), each opening its page.
 */
export default function ModelsPage() {
  return (
    <Suspense fallback={<Loading label="Loading models…" />}>
      <Models />
    </Suspense>
  );
}

function Models() {
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const policy = policyOfSearch(useSearchParams());
  const policyHref = usePolicyHref();
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
            href={policyHref(`/workspace/${workspaceId}/settings/models/catalog`)}
            className="org-settings-users-secondary-button"
            data-action="model-catalog"
            title="Every model the platform's AI modules bring, each with its page"
          >
            Model catalog
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
