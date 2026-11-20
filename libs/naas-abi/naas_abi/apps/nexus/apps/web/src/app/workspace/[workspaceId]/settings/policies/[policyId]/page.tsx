'use client';

import { WorkspaceAccess } from '../../workspace-access';

/** A policy's page: who holds it and at which level, then its document. */
export default function WorkspacePolicyPage() {
  return <WorkspaceAccess section="policies" />;
}
