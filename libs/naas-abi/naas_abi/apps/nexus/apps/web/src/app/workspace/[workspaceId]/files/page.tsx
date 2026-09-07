'use client';

import { useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import FilesBrowse from './browse/browse';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { filesBrowseHref, hasFilesDeepLink } from './lib/files-route';

/**
 * Desktop: /files is the file browser.
 * Mobile: /files is the drive list (workspace-layout renders FilesSection);
 * do not mount the browser here or its fetch effects fight the shell.
 *
 * A source/path query is a deep link into the browser. On mobile, send that
 * to /files/browse so the list-then-detail shell opens the folder/file.
 */
export default function FilesIndexPage() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const search = searchParams?.toString() ?? '';

  useEffect(() => {
    if (!isMobile || !hasFilesDeepLink(search)) return;
    router.replace(filesBrowseHref(workspaceId, search));
  }, [isMobile, search, router, workspaceId]);

  if (isMobile) return null;
  return <FilesBrowse />;
}
