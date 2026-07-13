'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useFilesStore } from '@/stores/files';
import { getWorkspacePath } from '@/components/shell/sidebar/utils';

// A drive object path always starts with `naas_abi/<drive-segment>/…`. Map the
// drive segment back to the Files-page source id so we can open the file there.
// (See driveRoot in files/page.tsx.)
const DRIVE_SEGMENT_TO_SOURCE: Record<string, string> = {
  'platform-drive': 'platform-drive',
  'my-drive': 'my-drive',
  'workspace-drive': 'workspace',
};

/**
 * Handles drive object-path links that were accidentally routed under /chat/
 * (e.g. `/chat/naas_abi/platform-drive/bob/…/LOreal.pptx`). These are not
 * conversation ids — treating them as one collapsed the URL to /chat/naas_abi.
 * Instead, send the user to the Files page for the matching drive and open the
 * file's preview, reusing the same store navigation the sidebar uses.
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
    const normalized = objectPath.replace(/^\/+|\/+$/g, '');
    const segments = normalized.split('/');
    const driveSegment = segments[1] ?? '';
    const source = DRIVE_SEGMENT_TO_SOURCE[driveSegment] ?? 'system-drive';

    const lastSegment = segments[segments.length - 1] ?? '';
    const isFile = lastSegment.includes('.');
    const parentPath = normalized.includes('/')
      ? normalized.slice(0, normalized.lastIndexOf('/'))
      : '';

    setStarredNavigation(
      isFile
        ? { source, path: parentPath, previewPath: normalized }
        : { source, path: normalized },
    );
    router.replace(getWorkspacePath(workspaceId, '/files'));
  }, [objectPath, workspaceId, router, setStarredNavigation]);

  return null;
}
