import { redirect } from 'next/navigation';

/** Legacy /organization/admins path; people management lives under Users. */
export default async function OrganizationAdminsRedirectPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  redirect(`/workspace/${workspaceId}/organization/users`);
}
