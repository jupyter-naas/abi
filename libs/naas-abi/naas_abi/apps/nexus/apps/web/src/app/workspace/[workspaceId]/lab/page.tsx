import { redirect } from 'next/navigation';

/** Lab is retired. Code owns editing. Old /lab bookmarks land on /code. */
export default function LabRedirectPage({
  params,
}: {
  params: { workspaceId: string };
}) {
  redirect(`/workspace/${params.workspaceId}/code`);
}
