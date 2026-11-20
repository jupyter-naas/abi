'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { settingsLandingPath } from '@/components/shell/settings-nav';
import { isMobileViewport, useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceSettingsAccessView } from '@/hooks/use-workspace-settings-access';

/**
 * `/workspace/<id>/settings`: a computer opens the workspace's first page the caller may
 * open; a phone stays here, where the layout lists Settings. Without access to the
 * workspace's settings, the list shows the other levels.
 */
export default function SettingsPage() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const workspaceId = useParams()?.workspaceId as string | undefined;
  const { access, iam } = useWorkspaceSettingsAccessView();

  useEffect(() => {
    if (isMobile || isMobileViewport() || !workspaceId || access === 'unknown') return;
    router.replace(access === 'none' ? '/account/profile' : `/workspace/${workspaceId}${settingsLandingPath(access, iam)}`);
  }, [isMobile, workspaceId, access, iam, router]);

  return null;
}
