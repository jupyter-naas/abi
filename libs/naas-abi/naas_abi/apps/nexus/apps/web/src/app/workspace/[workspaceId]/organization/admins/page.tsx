import { redirect } from 'next/navigation';

/** Legacy /organization/admins path; people management lives under Users. */
export default function OrganizationAdminsRedirectPage({
  params,
}: {
  params: { workspaceId: string };
}) {
  redirect(`/workspace/${params.workspaceId}/organization/users`);
}
