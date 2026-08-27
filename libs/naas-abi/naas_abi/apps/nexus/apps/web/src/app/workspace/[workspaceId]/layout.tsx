'use client';

import { useEffect, useLayoutEffect } from 'react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { getWorkspaceSwitchPath, isWorkspacePathAllowed, pathNeedsAgentCatalog, pathNeedsGraphExport } from '@/lib/feature-access';
import { GraphExportToastHost } from '@/components/graph/graph-export-toast-host';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';

export default function WorkspaceIdLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;

  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentWorkspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const syncWorkspaceConversations = useWorkspaceStore((s) => s.syncWorkspaceConversations);
  const contextPanelOpen = useWorkspaceStore((s) => s.contextPanelOpen);
  const token = useAuthStore((s) => s.token);
  const currentWorkspace = workspaces.find((w) => w.id === workspaceId);

  // Before paint, so section pages fetch the target workspace instead of
  // rendering one frame against the previous id.
  useLayoutEffect(() => {
    if (workspaceId && workspaceId !== currentWorkspaceId && currentWorkspace) {
      setCurrentWorkspace(workspaceId);
    }
  }, [workspaceId, currentWorkspaceId, currentWorkspace, setCurrentWorkspace]);

  useEffect(() => {
    if (!workspaceId) return;
    if (!contextPanelOpen && !pathNeedsAgentCatalog(pathname)) return;
    void syncWorkspaceConversations(workspaceId);
  }, [workspaceId, pathname, contextPanelOpen, syncWorkspaceConversations]);

  // Unknown id: wait for a fresh list before bouncing. A stale in-memory
  // list used to send people to workspaces[0] on the first paint of a switch,
  // which cancelled navigation to a workspace that was already in the dropdown.
  useEffect(() => {
    if (!workspaceId) return;
    if (workspaces.some((w) => w.id === workspaceId)) return;

    let cancelled = false;
    void useWorkspaceStore.getState().fetchWorkspaces().then(() => {
      if (cancelled) return;
      const list = useWorkspaceStore.getState().workspaces;
      if (list.some((w) => w.id === workspaceId)) return;
      if (list.length === 0) return;
      const fallback = list[0];
      router.replace(
        getWorkspaceSwitchPath({
          pathname: pathname || '',
          targetWorkspaceId: fallback.id,
          role: fallback.currentUserRole,
          workspaceFlags: fallback.featureFlags,
        }),
      );
    });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, workspaces, pathname, router]);

  useEffect(() => {
    if (!token || !workspaceId || !pathname || !currentWorkspace) {
      return;
    }

    const allowed = isWorkspacePathAllowed({
      pathname,
      role: currentWorkspace.currentUserRole,
      workspaceFlags: currentWorkspace.featureFlags,
    });
    if (allowed) {
      return;
    }

    const blockedPath = encodeURIComponent(pathname);
    const notAvailablePath = `/workspace/${workspaceId}/not-available?from=${blockedPath}`;
    if (notAvailablePath !== pathname) {
      router.replace(notAvailablePath);
    }
  }, [token, workspaceId, pathname, currentWorkspace, router]);

  return (
    <>
      {pathNeedsGraphExport(pathname) && <GraphExportToastHost workspaceId={workspaceId} />}
      {children}
    </>
  );
}
