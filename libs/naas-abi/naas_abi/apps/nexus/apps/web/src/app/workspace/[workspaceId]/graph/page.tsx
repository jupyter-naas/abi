import { redirect } from 'next/navigation';

export default function GraphPage({ params }: { params: { workspaceId: string } }) {
  redirect(`/workspace/${params.workspaceId}/graph/network`);
}
