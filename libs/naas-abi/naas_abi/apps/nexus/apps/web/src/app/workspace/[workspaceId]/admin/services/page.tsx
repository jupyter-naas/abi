import { redirect } from 'next/navigation';

/** Services moved under Settings → Services; keep the old URL working. */
export default async function AdminServicesRedirect({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  redirect(`/workspace/${workspaceId}/settings/services`);
}
