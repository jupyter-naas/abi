'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { orgSettingsSectionPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import { userAccess, type Fetcher } from './users-api';
import type { UserAccess } from './users-model';
import { Card } from '@/components/ui/card';

type Loaded = { state: 'loading' } | { state: 'error'; error: string } | { state: 'ready'; access: UserAccess };

/**
 * Platform › Users › a person › Organizations: the organizations they belong to, and those they
 * administer, read from their groups. Nothing to change here: each opens their page in that
 * organization (its Users), where their workspaces, groups and policies there are changed.
 * `personId` is their IAM id or their account id.
 */
export function PlatformOrganizations({ personId, nonce = 0, fetcher }: { personId: string; nonce?: number; fetcher?: Fetcher }) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  useEffect(() => {
    let live = true;
    setLoaded({ state: 'loading' });
    void (async () => {
      // One read by their IAM id or account id (#1608): the API finds the account, so the
      // directory is not downloaded to find it. Not found: no account (an invitee, a deleted one).
      const answer = await userAccess(personId, fetcher);
      if (!live) return;
      if (answer.ok) return setLoaded({ state: 'ready', access: answer.data });
      setLoaded({ state: 'error', error: answer.status === 404 ? 'They have no account yet.' : answer.error });
    })();
    return () => {
      live = false;
    };
  }, [personId, nonce, fetcher]);

  return (
    <Card
      title="Organizations"
      description="The organizations they belong to. Their workspaces, groups and policies there are changed on their page in each."
    >
      <div data-role-list="organizations">
        {loaded.state === 'loading' && <p className="text-sm text-muted-foreground">Loading…</p>}
        {loaded.state === 'error' && (
          <p className="text-sm text-muted-foreground" role="alert">
            {loaded.error}
          </p>
        )}
        {loaded.state === 'ready' &&
          (loaded.access.organizations.length === 0 ? (
            <p className="text-sm text-muted-foreground">In no organization.</p>
          ) : (
            <ul className="divide-y divide-border">
              {[...loaded.access.organizations]
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((org) => (
                  <li key={org.id} className="flex items-center justify-between gap-3 py-2" data-organization={org.id}>
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-foreground">{org.name}</span>
                      <span className="block text-xs text-muted-foreground">{org.org_admin ? 'Administers it' : 'Member'}</span>
                    </span>
                    <Link
                      href={`${orgSettingsSectionPath(org.id, 'users')}/${encodeURIComponent(loaded.access.user_id)}`}
                      className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      data-action="open-organization"
                    >
                      Their page there
                      <ChevronRight size={14} />
                    </Link>
                  </li>
                ))}
            </ul>
          ))}
      </div>
    </Card>
  );
}
