'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { mapsAllLayoutsPath } from './lib/maps-route';

/**
 * Desktop: /maps opens the All layouts map (every layout switched on, overlaid).
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
    router.replace(mapsAllLayoutsPath(workspaceId));
  }, [isMobile, router, workspaceId]);

  if (isMobile) return null;

  return (
    <div className="flex h-full items-center justify-center">
      <p className="text-sm text-muted-foreground">Opening All layouts…</p>
    </div>
  );
}
