'use client';

import { useEffect, useState } from 'react';
import { orgSettingsIndexPath } from '@/app/organizations/[orgId]/settings/lib/nav';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  openableOrganizations,
  useOrganizationSettingsAccess,
} from '@/hooks/use-organization-settings-access';
import { usePlatformSettingsAccess } from '@/hooks/use-platform-settings-access';
import { firstPlatformSettingsPath, PLATFORM_SETTINGS_INDEX, visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';
import { settingsScopeReturnPath } from '@/lib/settings-scope-path';

type ListedOrg = { id: string; name: string; current_user_role?: string | null };

export type AvatarSettingsLinks = {
  account: { label: string; href: string };
  organization: { label: string; href: string } | null;
  platform: { label: string; href: string } | null;
};

/**
 * Avatar menu destinations: Account, Organization, Platform (remembered paths).
 * and the same remembered paths as the settings scope switcher.
 */
export function useAvatarSettingsLinks(): AvatarSettingsLinks {
  const userId = useAuthStore((s) => s.user?.id);
  const canOrganization = useOrganizationSettingsAccess();
  const platformSettings = usePlatformSettingsAccess();
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const workspaceOrgId = useWorkspaceStore((s) =>
    s.workspaces.find((w) => w.id === s.currentWorkspaceId)?.organizationId
  );

  const [organization, setOrganization] = useState<AvatarSettingsLinks['organization']>(null);

  const accountHref = settingsScopeReturnPath({ kind: 'account' }, '/account/profile');

  const showPlatform =
    platformSettings.status === 'ready' &&
    visiblePlatformSettingsGroups(platformSettings.actions).length > 0;
  const platformHref = showPlatform
    ? settingsScopeReturnPath(
        { kind: 'platform' },
        firstPlatformSettingsPath(platformSettings.actions) ?? PLATFORM_SETTINGS_INDEX
      )
    : null;

  useEffect(() => {
    if (!canOrganization) {
      setOrganization(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const response = await authFetch('/api/organizations');
        if (!response.ok) {
          if (!cancelled) setOrganization(null);
          return;
        }
        const orgs = (await response.json()) as ListedOrg[];
        const open = await openableOrganizations(
          orgs.map((o) => ({ id: o.id, currentUserRole: o.current_user_role ?? null }))
        );
        if (cancelled) return;
        const pick =
          (workspaceOrgId && open.find((o) => o.id === workspaceOrgId)) ??
          (open.length === 1 ? open[0] : null);
        if (!pick) {
          setOrganization(null);
          return;
        }
        setOrganization({
          label: 'Organization',
          href: settingsScopeReturnPath(
            { kind: 'organization', orgId: pick.id },
            orgSettingsIndexPath(pick.id)
          ),
        });
      } catch {
        if (!cancelled) setOrganization(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canOrganization, workspaceOrgId, userId]);

  return {
    account: { label: 'Account', href: accountHref },
    organization,
    platform: platformHref ? { label: 'Platform', href: platformHref } : null,
  };
}