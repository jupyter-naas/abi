'use client';

import type { ReactNode } from 'react';
import { PlatformAccess } from '../platform-access';

/**
 * The list and a group's page (`[groupId]`) are one view, kept mounted across their addresses:
 * a click on a row opens the group at once, without reading the access, the list and the group
 * again (the pages render nothing of their own).
 */
export default function PlatformGroupsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <PlatformAccess section="groups" />
      {children}
    </>
  );
}
