import { redirect } from 'next/navigation';

export default function GraphPage({
  params,
  searchParams,
}: {
  params: { workspaceId: string };
  searchParams?: { view?: string };
}) {
  const base = `/workspace/${params.workspaceId}/graph`;
  const view = searchParams?.view;

  if (view === 'create-graph') {
    redirect(`${base}/create-graph`);
  }
  if (view === 'create-individual') {
    redirect(`${base}/create-individual`);
  }
  if (view === 'entities' || view === 'import' || view === 'sparql') {
    redirect(`${base}/explore${view ? `?view=${view}` : ''}`);
  }

  redirect(`${base}/network`);
}
