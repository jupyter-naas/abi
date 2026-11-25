'use client';

import type { ReactNode } from 'react';
import { OrgAccess } from '../components/org-access';

/**
 * The list and a group's page (`[groupId]`) are one view, kept mounted across their addresses:
 * a click on a row opens the group at once, without reading the access, the list and the group
 * again (the pages render nothing of their own).
 */
export default function OrgGroupsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <OrgAccess section="groups" />
      {children}
    </>
  );
}
