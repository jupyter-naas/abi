'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { ShieldCheck } from 'lucide-react';
import { createIamAdminApi, IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { OrganizationSetView, SetsView } from '@/lib/iam-admin/types';
import { SetsMatrix } from '@/app/settings/modules/sets-matrix';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import '../components/org-settings-components.css';
import './modules.css';

type Loaded =
  | { state: 'loading' }
  | { state: 'forbidden' }
  | { state: 'error'; message: string }
  | { state: 'ready'; view: SetsView; organization: OrganizationSetView };

const TITLE = 'Modules & features';
const SUBTITLE =
  'The module scopes and features this organization and each of its workspaces may use. A workspace never gets more than its organization.';

/**
 * Organization Settings › Modules & features: this organization's matrix (the organization, then
 * its workspaces). Who may change which column is the API's `editable`; `workspaceId` scrolls to
 * and highlights that workspace's column.
 */
export function OrgModulesView({
  api,
  orgId,
  workspaceId = null,
}: {
  api: IamAdminApi;
  orgId: string;
  workspaceId?: string | null;
}) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  useEffect(() => {
    let cancelled = false;
    setLoaded({ state: 'loading' });
    api
      .sets(orgId)
      .then((view) => {
        if (cancelled) return;
        const organization = view.organizations.find((o) => o.id === orgId);
        setLoaded(organization ? { state: 'ready', view, organization } : { state: 'forbidden' });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof IamAdminError && (e.status === 403 || e.status === 404)) setLoaded({ state: 'forbidden' });
        else setLoaded({ state: 'error', message: e instanceof Error ? e.message : String(e) });
      });
    return () => {
      cancelled = true;
    };
  }, [api, orgId]);

  const catalog = useMemo(
    () => (loaded.state === 'ready' ? { modules: loaded.view.modules, features: loaded.view.features } : null),
    [loaded],
  );

  if (loaded.state === 'forbidden') {
    return (
      <div className="org-settings-modules-page">
        <OrgSettingsPageHeader title={TITLE} subtitle={SUBTITLE} />
        <div className="org-settings-empty">
          <div className="org-settings-empty-icon">
            <ShieldCheck size={24} />
          </div>
          <p className="org-settings-empty-title">You cannot view this organization’s modules</p>
          <p className="org-settings-empty-body">
            The modules and features of an organization are shown to whoever may read its set. Ask an
            organization owner or admin.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="org-settings-modules-page">
      <OrgSettingsPageHeader title={TITLE} subtitle={SUBTITLE} />
      {loaded.state === 'loading' && <p className="org-settings-modules-note">Loading…</p>}
      {loaded.state === 'error' && (
        <p className="org-settings-modules-note" role="alert">
          {loaded.message}
        </p>
      )}
      {loaded.state === 'ready' && catalog && (
        <SetsMatrix
          api={api}
          catalog={catalog}
          organization={loaded.organization}
          onChange={(organization) => setLoaded({ ...loaded, organization })}
          highlightWorkspace={workspaceId}
        />
      )}
    </div>
  );
}

function OrgModulesRoute() {
  const params = useParams();
  const search = useSearchParams();
  const orgId = params.orgId as string;
  const api = useMemo(() => createIamAdminApi(), []);
  return <OrgModulesView api={api} orgId={orgId} workspaceId={search?.get('workspace') ?? null} />;
}

export default function OrgModulesPage() {
  return (
    <Suspense fallback={<p className="org-settings-modules-note">Loading…</p>}>
      <OrgModulesRoute />
    </Suspense>
  );
}
