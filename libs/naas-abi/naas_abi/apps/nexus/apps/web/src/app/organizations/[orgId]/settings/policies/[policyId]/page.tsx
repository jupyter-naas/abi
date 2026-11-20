'use client';

import { OrgAccess } from '../../components/org-access';

/** A policy's page: who holds it and at which level, then its document. */
export default function OrgPolicyPage() {
  return <OrgAccess section="policies" />;
}
