import { redirect } from 'next/navigation';

/** Legacy /settings/admins path; org people management lives under Users. */
export default async function AdminsRedirectPage({
  params,
}: {
  params: Promise<{ orgId: string }>;
}) {
  const { orgId } = await params;
  redirect(`/organizations/${orgId}/settings/users`);
}
