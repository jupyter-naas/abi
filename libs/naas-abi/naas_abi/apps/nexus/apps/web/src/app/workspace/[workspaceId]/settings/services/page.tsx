import { redirect } from 'next/navigation';
import { DOCKER_SERVICES } from '@/lib/docker-services';

export default function ServicesPage({ params }: { params: { workspaceId: string } }) {
  redirect(`/workspace/${params.workspaceId}/settings/services/${DOCKER_SERVICES[0]?.id ?? ''}`);
}
