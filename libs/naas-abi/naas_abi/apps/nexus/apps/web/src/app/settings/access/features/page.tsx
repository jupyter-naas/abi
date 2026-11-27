'use client';

/** Platform settings › Access › Features: what the platform offers every organization ("Platform
 *  access", first and by default), or an organization's Features (its "<O> access"), picked atop. */
import { FeatureAccess } from '@/app/workspace/[workspaceId]/settings/features/feature-access';
import { PLATFORM_TARGET } from '@/lib/access-model/target';
import { OrganizationOffer } from '../organization-offer';
import { PlatformFeatures } from '../platform-features';

export default function PlatformFeaturesPage() {
  return (
    <OrganizationOffer
      platform
      render={({ target, initialPolicy, onPolicyChange, pickerPrefix }) =>
        target === PLATFORM_TARGET ? (
          <PlatformFeatures pickerPrefix={pickerPrefix} />
        ) : (
          <FeatureAccess
            workspaceId={target}
            initialPolicy={initialPolicy}
            onPolicyChange={onPolicyChange}
            pickerPrefix={pickerPrefix}
          />
        )
      }
    />
  );
}
