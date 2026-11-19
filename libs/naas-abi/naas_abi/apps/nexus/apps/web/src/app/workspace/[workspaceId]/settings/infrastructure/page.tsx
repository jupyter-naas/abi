import { redirect } from 'next/navigation';
import { INFRASTRUCTURE_LAYERS_PATH } from '@/components/shell/settings-nav';

/** Infrastructure is two pages now, Layers and Diagrams. Old links land on Layers. */
export default async function InfrastructureRedirectPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  redirect(`/workspace/${workspaceId}${INFRASTRUCTURE_LAYERS_PATH}`);
}
