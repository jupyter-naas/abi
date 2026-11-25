'use client';

import type { ReactNode } from 'react';
import { OrgAccess } from '../components/org-access';

/**
 * The list and a policy's page (`[policyId]`) are one view, kept mounted across their addresses:
 * a click on a row opens the policy at once, without reading the access, the list and the policy
 * again (the pages render nothing of their own).
 */
export default function OrgPoliciesLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <OrgAccess section="policies" />
      {children}
    </>
  );
}
