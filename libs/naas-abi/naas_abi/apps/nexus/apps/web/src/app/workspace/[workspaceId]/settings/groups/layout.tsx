'use client';

import type { ReactNode } from 'react';
import { WorkspaceAccess } from '../workspace-access';

/**
 * The list and a group's page (`[groupId]`) are one view, kept mounted across their addresses:
 * a click on a row opens the group at once, without reading the access, the list and the group
 * again (the pages render nothing of their own).
 */
export default function WorkspaceGroupsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <WorkspaceAccess section="groups" />
      {children}
    </>
  );
}
