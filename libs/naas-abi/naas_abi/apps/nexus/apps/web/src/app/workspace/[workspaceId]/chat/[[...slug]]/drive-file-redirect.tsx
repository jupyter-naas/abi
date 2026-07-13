'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useFilesStore } from '@/stores/files';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';
import { driveNavigationFor } from '@/lib/drive-links';

/**
 * Safety net for drive object-path links that still reach /chat/ (e.g. a shared
 * or bookmarked `/chat/naas_abi/platform-drive/bob/…/LOreal.pptx` URL). These
 * are not conversation ids — treating one as a conversation collapsed the URL to
 * /chat/naas_abi. Send the user to the Files page for the matching drive and open
 * the file's preview, reusing the same store navigation the sidebar uses.
 *
 * In-chat clicks are handled upstream by the markdown link renderer
 * (see isDriveObjectPath in chat-interface.tsx), so they never hit /chat/.
 */
export function DriveFileRedirect({
  workspaceId,
  objectPath,
}: {
  workspaceId: string;
  objectPath: string;
}) {
  const router = useRouter();
  const setStarredNavigation = useFilesStore((s) => s.setStarredNavigation);

  useEffect(() => {
    setStarredNavigation(driveNavigationFor(objectPath));
    router.replace(getWorkspacePath(workspaceId, '/files'));
  }, [objectPath, workspaceId, router, setStarredNavigation]);

  return null;
}
