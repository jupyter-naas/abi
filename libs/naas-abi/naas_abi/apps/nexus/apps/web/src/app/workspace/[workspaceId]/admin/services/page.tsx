import { redirect } from 'next/navigation';

/** Services moved under Settings → Services; keep the old URL working. */
export default function AdminServicesRedirect({ params }: { params: { workspaceId: string } }) {
  redirect(`/workspace/${params.workspaceId}/settings/services`);
}
