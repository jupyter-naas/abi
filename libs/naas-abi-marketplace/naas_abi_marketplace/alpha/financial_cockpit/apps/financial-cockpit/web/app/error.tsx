'use client';

import { useEffect } from 'react';

import { Button } from '@/components/ui/Button';

type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center bg-[var(--bg)]">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="max-w-md text-sm text-[var(--text-muted)]">
        The portal hit an unexpected problem. You can try again or go back to the
        home page.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onPress={reset} className="!w-auto">
          Try again
        </Button>
        <Button variant="ghost" onPress={() => window.location.assign('/')} className="!w-auto">
          Home
        </Button>
      </div>
    </div>
  );
}
