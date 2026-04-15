'use client';

import { Suspense, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';

function MagicLinkPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { verifyMagicLink, isLoading, error, clearError, isAuthenticated } = useAuthStore();

  const token = searchParams.get('token');
  const redirect = useMemo(() => {
    const requested = searchParams.get('redirect');
    if (!requested || !requested.startsWith('/')) {
      return '/';
    }
    return requested;
  }, [searchParams]);

  useEffect(() => {
    if (!token) {
      return;
    }
    clearError();
    verifyMagicLink(token).then((ok) => {
      if (ok) {
        router.replace(redirect);
      }
    });
  }, [token, verifyMagicLink, router, redirect, clearError]);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace(redirect);
    }
  }, [isAuthenticated, router, redirect]);

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md rounded-xl border p-6 text-center">
          <div className="mb-4 flex justify-center text-destructive">
            <AlertCircle className="h-8 w-8" />
          </div>
          <h1 className="text-lg font-semibold">Invalid magic link</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            This link is missing a token. Request a new sign-in link.
          </p>
          <Link href="/auth/login" className="mt-4 inline-block text-sm font-medium underline">
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border p-6 text-center">
        <div className="mb-4 flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
        <h1 className="text-lg font-semibold">Signing you in</h1>
        <p className="mt-2 text-sm text-muted-foreground">Please wait while we verify your magic link.</p>
        {error && (
          <p className="mt-4 text-sm text-destructive">{error}</p>
        )}
      </div>
    </div>
  );
}

function MagicLinkPageFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border p-6 text-center">
        <div className="mb-4 flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
        <h1 className="text-lg font-semibold">Loading magic link</h1>
        <p className="mt-2 text-sm text-muted-foreground">Please wait while we prepare sign-in.</p>
      </div>
    </div>
  );
}

export default function MagicLinkPage() {
  return (
    <Suspense fallback={<MagicLinkPageFallback />}>
      <MagicLinkPageContent />
    </Suspense>
  );
}
