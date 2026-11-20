'use client';

import '../access-base.css';
import '../access.css';

import { useMemo } from 'react';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { createAccessDirectory, type AccessDirectory } from '../access-directory';
import type { AccessNavigation } from '../access-props';
import type { AccessScope } from '../access-scope';
import { opensSection } from '../access-sections';
import type { BuiltInRole, RoleTarget } from '../roles/role-change';
import { PersonView } from './person';

/**
 * A person's page at a level (Platform › Users, an organization's or a workspace's Members):
 * every role, policy and group they hold, at every level IAM lets the caller list, attached,
 * detached and changed where IAM lets the caller (`PersonView`), and View as where it lets them
 * view as the person. The level's access (`GET /access?scope=`) decides the buttons; a group
 * opens its page where that level's Groups is shown (``groupHref``).
 */
export function PersonPage({
  scope,
  personId,
  label,
  nonce = 0,
  navigate,
  groupHref,
  onBack,
  backLabel,
  api,
  directory,
  changeRole,
}: {
  scope: AccessScope;
  personId: string;
  label?: string | null;
  nonce?: number;
  navigate: (href: string) => void;
  /** A group's page at this level, or null where there is none. */
  groupHref: ((groupId: string) => string) | null;
  onBack?: () => void;
  backLabel?: string;
  /** Tests pass fakes; the pages use the real API and member routes. */
  api?: IamAdminApi;
  directory?: AccessDirectory;
  changeRole?: (target: RoleTarget, userId: string, role: BuiltInRole) => Promise<void>;
}) {
  const client = useMemo(() => api ?? createIamAdminApi(), [api]);
  const people = useMemo(() => directory ?? createAccessDirectory(), [directory]);
  const { access, loading, error, can } = useIamAccess(scope.value ?? undefined, client, { reload: nonce });
  const showsGroups = !!groupHref && opensSection(access, 'groups');
  const open = useMemo<AccessNavigation>(
    () => ({ group: showsGroups ? (id) => navigate(groupHref!(id)) : undefined }),
    [showsGroups, groupHref, navigate],
  );
  if (loading) return <p className="access-empty">Loading…</p>;
  if (error) {
    return (
      <p className="access-source-note" role="status">
        <strong>Access unavailable.</strong> {error}
      </p>
    );
  }
  return (
    <div className="access-tab">
      <PersonView
        api={client}
        can={can}
        scope={scope}
        directory={people}
        nonce={nonce}
        open={open}
        personId={personId}
        label={label}
        onClose={onBack}
        backLabel={backLabel}
        {...(changeRole ? { changeRole } : {})}
      />
    </div>
  );
}
