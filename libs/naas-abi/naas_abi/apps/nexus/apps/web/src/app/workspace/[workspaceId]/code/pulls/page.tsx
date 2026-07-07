'use client';

// The pull-request UI now lives under the per-repo route
// (code/r/[owner]/[repo]/pulls) so URLs mirror GitHub. This legacy path
// redirects to the selected repo's pulls view, preserving any query string
// (e.g. ?new=1&source=… deep-links from the branches page).
import { useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useEnsureSelectedRepo } from '@/stores/code';

export default function PullsRedirect() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  const repoId = useEnsureSelectedRepo(workspaceId);

  useEffect(() => {
    if (!workspaceId || !repoId) return;
    const qs = search.toString();
    router.replace(`/workspace/${workspaceId}/code/r/${repoId}/pulls${qs ? `?${qs}` : ''}`);
  }, [workspaceId, repoId, router, search]);

  return (
    <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
      <Loader2 size={16} className="animate-spin" /> Redirecting…
    </div>
  );
}
