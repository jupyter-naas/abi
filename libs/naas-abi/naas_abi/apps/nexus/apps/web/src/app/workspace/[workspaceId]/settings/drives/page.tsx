import { redirect } from 'next/navigation';
import { DEFAULT_SETTINGS_PATH } from '@/components/shell/settings-nav';

/**
 * Workspace settings › Drives is gone: drives are the platform's storage backends,
 * listed in Platform Settings › Drives (`/settings/drives`), and who opens which view
 * of them is IAM's. Its old URL opens Workspace settings.
 */
export default async function DrivesSettingsRedirect({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  redirect(`/workspace/${workspaceId}${DEFAULT_SETTINGS_PATH}`);
}
