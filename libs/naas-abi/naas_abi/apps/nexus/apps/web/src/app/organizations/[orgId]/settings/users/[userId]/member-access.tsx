'use client';

import { useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { organizationAccessPath } from '@/components/access/access-paths';
import { organizationAccessScope } from '@/components/access/access-scope';
import { PersonPage } from '@/components/access/people/person-page';

/**
 * A member's roles and policies at every level IAM lets the caller list, on their page in the
 * organization's Members (`PersonPage` at the organization's scope): attached, detached and
 * changed where IAM lets the caller, and View as. Whoever opens the organization's Access and is
 * not one of its admins sees this alone.
 */
export function MemberAccess({ orgId, personId }: { orgId: string; personId: string }) {
  const router = useRouter();
  const navigate = useCallback((href: string) => router.push(href), [router]);
  const groupHref = useCallback((id: string) => organizationAccessPath(orgId, 'groups', id), [orgId]);
  const scope = useMemo(() => organizationAccessScope(orgId), [orgId]);
  return (
    <section className="org-member-detail-section" aria-label="Roles and policies">
      <header className="org-member-detail-section-header">
        <h3>Roles and policies</h3>
        <p>What they hold at every level you may see, where it comes from, and its groups.</p>
      </header>
      <PersonPage scope={scope} personId={personId} navigate={navigate} groupHref={groupHref} />
    </section>
  );
}
