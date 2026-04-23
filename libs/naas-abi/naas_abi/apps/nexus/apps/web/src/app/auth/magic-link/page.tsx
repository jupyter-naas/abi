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

  const handleConfirmSignIn = () => {
    if (!token || isLoading) {
      return;
    }
    clearError();
    verifyMagicLink(token).then((ok) => {
      if (ok) {
        router.replace(redirect);
      }
    });
  };

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
          <AlertCircle className="h-8 w-8 text-primary" />
        </div>
        <h1 className="text-lg font-semibold">Confirm sign-in</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          To continue, click the button below to confirm your sign-in request.
        </p>
        <button
          type="button"
          onClick={handleConfirmSignIn}
          disabled={isLoading}
          className="mt-4 inline-flex w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Verifying...
            </>
          ) : (
            'Click to confirm sign-in'
          )}
        </button>
        {error && (
          <p className="mt-4 text-sm text-destructive">{error}</p>
        )}
        <Link href="/auth/login" className="mt-4 inline-block text-sm font-medium underline">
          Back to sign in
        </Link>
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
