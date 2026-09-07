'use client';

// Code review moved into the unified Code sub-app (/code/pulls). Kept as a
// redirect so old links/bookmarks keep working.
import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function ReviewRedirect() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  useEffect(() => {
    if (workspaceId) router.replace(`/workspace/${workspaceId}/code/pulls`);
  }, [workspaceId, router]);
  return null;
}
