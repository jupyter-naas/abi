'use client';

import { useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useWorkspaceStore } from '@/stores/workspace';
import { OfficeCreateLoader } from './office-create-loader';
import {
  clearOfficeCreate,
  isOfficeCreateNewPath,
  isOfficeCreateProjectPath,
  prefetchOfficeCreate,
  useOfficeCreateStore,
} from './office-create-state';

function useOfficeCreatePrefetch() {
  const router = useRouter();
  const pathname = usePathname();
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);

  useEffect(() => {
    if (!workspaceId) return;
    if (pathname?.includes('/documents')) {
      prefetchOfficeCreate(router, 'document', workspaceId);
    }
    if (pathname?.includes('/slides')) {
      prefetchOfficeCreate(router, 'deck', workspaceId);
    }
  }, [pathname, router, workspaceId]);
}

function useOfficeCreateRouteSync(pathname: string | null) {
  const kind = useOfficeCreateStore((s) => s.kind);
  const seenNew = useRef(false);

  useEffect(() => {
    if (!kind) {
      seenNew.current = false;
      return;
    }
    if (isOfficeCreateNewPath(pathname)) {
      seenNew.current = true;
      return;
    }
    // Hold the letter overlay until the editor fetches HTML. Sidecar can
    // still be starting; the page clears this flag after the GET succeeds.
    if (seenNew.current && isOfficeCreateProjectPath(pathname)) {
      return;
    }
    if (seenNew.current) clearOfficeCreate();
  }, [kind, pathname]);
}

/** Covers the open office surface the instant File → New sets the store flag. */
export function OfficeCreateOverlay() {
  const pathname = usePathname();
  const kind = useOfficeCreateStore((s) => s.kind);
  const phase = useOfficeCreateStore((s) => s.phase);
  const error = useOfficeCreateStore((s) => s.error);
  useOfficeCreatePrefetch();
  useOfficeCreateRouteSync(pathname);

  if (!kind) return null;

  return (
    <div
      className="absolute inset-0 z-20 flex flex-col bg-background"
      data-testid="office-create-overlay"
    >
      <OfficeCreateLoader kind={kind} phase={phase} error={error} />
    </div>
  );
}
