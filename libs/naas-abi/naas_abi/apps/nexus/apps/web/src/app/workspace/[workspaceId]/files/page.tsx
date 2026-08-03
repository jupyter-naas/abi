'use client';

import FilesBrowse from './browse/browse';
import { useIsMobile } from '@/hooks/use-is-mobile';

/**
 * Desktop: /files is the file browser.
 * Mobile: /files is the drive list (workspace-layout renders FilesSection);
 * do not mount the browser here or its fetch effects fight the shell.
 */
export default function FilesIndexPage() {
  const isMobile = useIsMobile();
  if (isMobile) return null;
  return <FilesBrowse />;
}
