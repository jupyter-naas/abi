'use client';

import type { ReactNode } from 'react';
import { PlatformAccess } from '../platform-access';

/**
 * The list and a policy's page (`[policyId]`) are one view, kept mounted across their addresses:
 * a click on a row opens the policy at once, without reading the access, the list and the policy
 * again (the pages render nothing of their own).
 */
export default function PlatformPoliciesLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <PlatformAccess section="policies" />
      {children}
    </>
  );
}
