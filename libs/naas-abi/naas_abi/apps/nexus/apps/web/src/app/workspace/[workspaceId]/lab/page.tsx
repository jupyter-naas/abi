'use client';

import { useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';

/** Legacy route: Lab was replaced by Code. Keep redirect for bookmarks and old links. */
export default function LabRedirect() {
  const router = useRouter();
  const params = useParams();

  useEffect(() => {
    const workspaceId = params?.workspaceId as string;
    router.replace(workspaceId ? `/workspace/${workspaceId}/code` : '/code');
  }, [router, params]);

  return null;
}
