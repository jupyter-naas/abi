'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function CodeIndex() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = typeof params?.workspaceId === 'string' ? params.workspaceId : '';
  useEffect(() => {
    if (workspaceId) router.replace(`/workspace/${workspaceId}/code/repos`);
  }, [workspaceId, router]);
  return null;
}
