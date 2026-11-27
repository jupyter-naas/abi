'use client';

/** Platform settings › Access › Features: an organization's Features (its "<O> access"), picked atop. */
import { FeatureAccess } from '@/app/workspace/[workspaceId]/settings/features/feature-access';
import { OrganizationOffer } from '../organization-offer';

export default function PlatformFeaturesPage() {
  return (
    <OrganizationOffer
      render={({ target, initialPolicy, onPolicyChange }) => (
        <FeatureAccess workspaceId={target} initialPolicy={initialPolicy} onPolicyChange={onPolicyChange} />
      )}
    />
  );
}
