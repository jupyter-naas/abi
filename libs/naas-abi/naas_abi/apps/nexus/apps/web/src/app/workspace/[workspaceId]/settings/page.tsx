import { redirect } from 'next/navigation';
import { DEFAULT_SETTINGS_PATH } from '@/components/shell/settings-nav';

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  redirect(`/workspace/${workspaceId}${DEFAULT_SETTINGS_PATH}`);
}
