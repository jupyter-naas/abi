import { redirect } from 'next/navigation';

/** Lab is retired. Code owns editing. Old /lab bookmarks land on /code. */
export default async function LabRedirectPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  redirect(`/workspace/${workspaceId}/code`);
}
