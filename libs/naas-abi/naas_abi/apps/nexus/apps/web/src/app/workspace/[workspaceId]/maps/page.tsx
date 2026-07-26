'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { mapsDatasetPath } from './lib/maps-route';

/**
 * Desktop: /maps auto-opens the presence primer (land-on-Maps product intent).
 * Mobile: /maps is the dataset library list (workspace-layout renders MapsSection).
 */
export default function MapsIndexPage() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const params = useParams();
  const workspaceId =
    typeof params?.workspaceId === 'string' ? params.workspaceId : null;

  useEffect(() => {
    if (isMobile) return;
    router.replace(mapsDatasetPath(workspaceId, 'presence'));
  }, [isMobile, router, workspaceId]);

  if (isMobile) return null;

  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-sm text-muted-foreground">Opening Here…</p>
    </div>
  );
}
