'use client';

/** Platform settings › Access › Modules: an organization's Modules (its "<O> access"), picked atop. */
import { WorkspaceModules } from '@/app/workspace/[workspaceId]/settings/modules/modules';
import { OrganizationOffer } from '../organization-offer';

export default function PlatformModulesPage() {
  return (
    <OrganizationOffer
      render={({ target, initialPolicy, onPolicyChange }) => (
        <WorkspaceModules workspaceId={target} initialPolicy={initialPolicy} onPolicyChange={onPolicyChange} />
      )}
    />
  );
}
