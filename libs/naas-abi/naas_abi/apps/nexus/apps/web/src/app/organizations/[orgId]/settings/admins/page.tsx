import { redirect } from 'next/navigation';

/** Legacy /settings/admins path; org people management lives under Users. */
export default function AdminsRedirectPage({
  params,
}: {
  params: { orgId: string };
}) {
  redirect(`/organizations/${params.orgId}/settings/users`);
}
