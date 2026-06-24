'use client';

// The IDE moved into the unified Code sub-app (/code/workspaces). Kept as a
// redirect so old links/bookmarks keep working.
import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function IdeRedirect() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  useEffect(() => {
    if (workspaceId) router.replace(`/workspace/${workspaceId}/code/workspaces`);
  }, [workspaceId, router]);
  return null;
}
