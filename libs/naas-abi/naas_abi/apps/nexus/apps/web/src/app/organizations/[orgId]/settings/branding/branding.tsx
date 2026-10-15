'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { orgSettingsSectionPath } from '../lib/nav';

/** Branding lives under General; keep this route as a redirect for old links. */
export default function BrandingRedirectPage() {
  const router = useRouter();
  const orgId = useParams()?.orgId as string;

  useEffect(() => {
    if (orgId) {
      router.replace(orgSettingsSectionPath(orgId, 'general'));
    }
  }, [orgId, router]);

  return null;
}
