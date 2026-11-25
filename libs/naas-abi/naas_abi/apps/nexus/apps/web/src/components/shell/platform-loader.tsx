'use client';

/**
 * Shown while the platform is reached after a sign-in or a reload: the workspaces (their client,
 * their colors) are read before any page shows. `retrying`: the API did not answer yet (it may be
 * starting); it is asked again.
 */
export function PlatformLoader({ retrying = false }: { retrying?: boolean }) {
  return (
    <div className="flex h-screen items-center justify-center bg-background" role="status" aria-live="polite" data-platform-loader="">
      <div className="text-center">
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">{retrying ? 'The platform is starting… retrying' : 'Loading your workspaces…'}</p>
      </div>
    </div>
  );
}
