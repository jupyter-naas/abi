import { redirect } from 'next/navigation';

export default async function GraphPage({
  params,
  searchParams,
}: {
  params: Promise<{ workspaceId: string }>;
  searchParams?: Promise<{ view?: string }>;
}) {
  const { workspaceId } = await params;
  const base = `/workspace/${workspaceId}/graph`;
  const view = (await searchParams)?.view;

  if (view === 'create-graph') {
    redirect(`${base}/create-graph`);
  }
  if (view === 'create-individual') {
    redirect(`${base}/create-individual`);
  }

  if (view === 'entities') redirect(`${base}/network`);
  redirect(`${base}/explorer`);
}
