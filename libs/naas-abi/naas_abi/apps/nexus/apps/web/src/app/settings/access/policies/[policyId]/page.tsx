'use client';

import { PlatformAccess } from '../../platform-access';

/** A policy's page: who holds it and at which level, then its document. */
export default function PlatformPolicyPage() {
  return <PlatformAccess section="policies" />;
}
