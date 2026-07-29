'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { orgSettingsSectionPath } from './lib/nav';

export default function OrganizationSettingsIndexPage() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const params = useParams();
  const orgId = params.orgId as string;

  // Desktop keeps the old default: land on General. Mobile stays on /settings
  // so the layout can show the settings list first (account-style list-then-detail).
  useEffect(() => {
    if (!isMobile && orgId) {
      router.replace(orgSettingsSectionPath(orgId, 'general'));
    }
  }, [isMobile, orgId, router]);

  return null;
}
