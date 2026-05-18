'use client';

import { useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';

export default function LabRedirect() {
  const router = useRouter();
  const params = useParams();

  useEffect(() => {
    const workspaceId = params?.workspaceId as string;
    router.replace(workspaceId ? `/workspace/${workspaceId}/code` : '/code');
  }, [router, params]);

  return null;
}
