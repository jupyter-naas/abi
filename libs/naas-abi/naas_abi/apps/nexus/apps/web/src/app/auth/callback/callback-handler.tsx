'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { safeNextPath } from '@/lib/auth-session';
import { useAuthStore } from '@/stores/auth';

/**
 * The API set the session cookie: read the session (user and CSRF token, kept
 * in memory) and go on. Nothing here sees or stores a token.
 */
export default function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    let cancelled = false;
    const next = safeNextPath(searchParams.get('next'));
    void useAuthStore
      .getState()
      .adoptCookieSession()
      .then((adopted) => {
        if (cancelled) return;
        router.replace(adopted ? next : '/auth/login?sso_error=sign_in_failed');
      });
    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}
