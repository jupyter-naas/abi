'use client';

/** Platform settings › Access › Services: an organization's Services (its "<O> access"), picked atop. */
import { CoreServices } from '@/app/workspace/[workspaceId]/settings/core-services/core-services';
import { OrganizationOffer } from '../organization-offer';

export default function PlatformServicesPage() {
  return (
    <OrganizationOffer
      render={({ target, initialPolicy, onPolicyChange }) => (
        <CoreServices workspaceId={target} initialPolicy={initialPolicy} onPolicyChange={onPolicyChange} />
      )}
    />
  );
}
