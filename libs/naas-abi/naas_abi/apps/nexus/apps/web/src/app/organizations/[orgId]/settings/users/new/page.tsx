'use client';

import { useParams, useRouter } from 'next/navigation';
import { useOrganizationStore } from '@/stores/organization';
import { CreateUserForm } from '@/components/people/create-user-form';
import { createdMessage } from '@/lib/people';
import { orgSettingsSectionPath } from '../../lib/nav';

/**
 * Create user (Organization settings › Users): the shared create form, with this organization
 * fixed, an org role (or none: workspace access only, once a workspace is picked) and the
 * organization's workspaces to pick. One request creates the person (or links their account)
 * with every role.
 */
export default function OrgCreateUserPage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const organization = useOrganizationStore((s) => s.organizations.find((o) => o.id === orgId));
  const usersPath = orgSettingsSectionPath(orgId, 'users');

  return (
    <CreateUserForm
      organization={{ fixed: { id: orgId, name: organization?.name ?? '' } }}
      orgRoles={['member', 'admin']}
      workspaceRoles={['member', 'viewer', 'admin']}
      subtitle="Add someone to this organization. They are created at once and invited until they first sign in; an email that already has an account is linked to it. Their account is created at the identity provider if it does not exist yet."
      back={{ href: usersPath, label: 'Users' }}
      onCancel={() => router.push(usersPath)}
      onForbidden={() => router.replace(usersPath)}
      onCreated={(created) => {
        // An org member has a page here; someone with workspace access only is listed in Users.
        if (created.member) {
          router.push(`${usersPath}/${encodeURIComponent(created.user.id)}`);
          return;
        }
        return createdMessage(created, organization?.name || 'the organization');
      }}
    />
  );
}
