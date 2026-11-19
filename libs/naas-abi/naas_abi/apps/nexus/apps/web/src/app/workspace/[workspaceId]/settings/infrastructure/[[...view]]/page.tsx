import { redirect } from 'next/navigation';
import {
  INFRASTRUCTURE_DIAGRAMS_PATH,
  INFRASTRUCTURE_LAYERS_PATH,
} from '@/app/settings/system/system-tabs';

/** The map of the code is the platform's, in the Console (System › Layers, Diagrams). */
export default async function InfrastructureRedirectPage({
  params,
}: {
  params: Promise<{ view?: string[] }>;
}) {
  const { view } = await params;
  redirect(view?.[0] === 'diagrams' ? INFRASTRUCTURE_DIAGRAMS_PATH : INFRASTRUCTURE_LAYERS_PATH);
}
