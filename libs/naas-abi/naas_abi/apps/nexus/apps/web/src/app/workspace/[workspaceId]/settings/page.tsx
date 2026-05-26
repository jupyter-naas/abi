import { redirect } from 'next/navigation';
import { DEFAULT_SETTINGS_PATH } from '@/components/shell/settings-nav';

export default function SettingsPage({ params }: { params: { workspaceId: string } }) {
  redirect(`/workspace/${params.workspaceId}${DEFAULT_SETTINGS_PATH}`);
}
