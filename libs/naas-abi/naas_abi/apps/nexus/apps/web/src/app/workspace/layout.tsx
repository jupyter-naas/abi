'use client';

import { Component, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { WorkspaceLayout } from '@/components/shell/workspace-layout';
import { ShellTitleProvider } from '@/components/shell/shell-title';
import { useWorkspaceStore } from '@/stores/workspace';
import { clearAuthFlagCookie } from '@/lib/auth-session';
import { useAuthStore } from '@/stores/auth';

// Catches unhandled promise rejections (not caught by React error boundaries)
// Next.js uses thrown sentinels (NEXT_REDIRECT, NEXT_NOT_FOUND) to drive
// navigation from Server Components. They are not real errors and must not
// surface in any user-facing error UI.
function isNextNavigationSentinel(reason: unknown): boolean {
  if (!reason) return false;
  const digest = (reason as { digest?: unknown }).digest;
  if (typeof digest === 'string' && digest.startsWith('NEXT_')) return true;
  const message = (reason as { message?: unknown }).message;
  if (typeof message === 'string' && (message === 'NEXT_REDIRECT' || message === 'NEXT_NOT_FOUND')) {
    return true;
  }
  return false;
}

function AsyncErrorCatcher() {
  const [asyncError, setAsyncError] = useState<string | null>(null);

  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      if (isNextNavigationSentinel(event.reason)) {
        event.preventDefault();
        return;
      }
      const msg = event.reason?.message || event.reason?.toString() || 'Unknown async error';
      const stack = event.reason?.stack || '';
      console.error('[NEXUS Unhandled Rejection]', msg, stack);
      setAsyncError(`${msg}\n\n${stack}`);
      event.preventDefault();
    };

    const handleError = (event: ErrorEvent) => {
      if (isNextNavigationSentinel(event.error) || event.message === 'Uncaught Error: NEXT_REDIRECT' || event.message === 'Uncaught Error: NEXT_NOT_FOUND') {
        return;
      }
      console.error('[NEXUS Global Error]', event.message, event.error?.stack);
      setAsyncError(`${event.message}\n\n${event.error?.stack || ''}`);
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    window.addEventListener('error', handleError);
    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
      window.removeEventListener('error', handleError);
    };
  }, []);

  if (!asyncError) return null;

  return (
    <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 99999, maxWidth: 500, backgroundColor: '#1a1a2e', border: '2px solid #e94560', borderRadius: 8, padding: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: '#ff6b6b', fontWeight: 'bold', fontSize: 14 }}>Async Error Caught</span>
        <button onClick={() => setAsyncError(null)} style={{ color: '#a8a8a8', background: 'none', border: 'none', fontSize: 18, cursor: 'pointer' }}>x</button>
      </div>
      <pre style={{ color: '#a8a8a8', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 200, overflow: 'auto', margin: 0 }}>{asyncError}</pre>
    </div>
  );
}

// Error boundary to catch React rendering crashes and show a useful message
class WorkspaceErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[WorkspaceErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', width: '100vw', backgroundColor: '#1a1a2e', padding: 32 }}>
            <div style={{ maxWidth: 600, textAlign: 'center' }}>
              <h2 style={{ color: '#ff6b6b', fontSize: 24, fontWeight: 'bold', marginBottom: 16 }}>NEXUS Crash Report</h2>
              <div style={{ backgroundColor: '#16213e', border: '1px solid #e94560', borderRadius: 8, padding: 16, textAlign: 'left', marginBottom: 16, maxHeight: 300, overflow: 'auto' }}>
                <p style={{ color: '#ff6b6b', fontSize: 14, fontWeight: 'bold', marginBottom: 8 }}>{this.state.error?.message}</p>
                <pre style={{ color: '#a8a8a8', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {this.state.error?.stack}
                </pre>
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
                <button
                  onClick={() => this.setState({ hasError: false, error: null })}
                  style={{ backgroundColor: '#e94560', color: 'white', border: 'none', borderRadius: 6, padding: '8px 20px', fontSize: 14, cursor: 'pointer' }}
                >
                  Try again
                </button>
                <button
                  onClick={() => {
                    localStorage.removeItem('nexus-workspace-storage');
                    localStorage.removeItem('nexus-auth-storage');
                    window.location.href = '/auth/login';
                  }}
                  style={{ backgroundColor: '#16213e', color: '#e94560', border: '1px solid #e94560', borderRadius: 6, padding: '8px 20px', fontSize: 14, cursor: 'pointer' }}
                >
                  Clear cache &amp; login
                </button>
              </div>
            </div>
          </div>
          <div hidden>{this.props.children}</div>
        </>
      );
    }
    return this.props.children;
  }
}

export default function WorkspaceShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();

  const { workspaces, fetchWorkspaces } = useWorkspaceStore();
  const { token } = useAuthStore();
  const [authReady, setAuthReady] = useState(false);
  const [membershipChecked, setMembershipChecked] = useState(false);

  // Wait for the auth store to rehydrate from localStorage, then silently
  // validate / refresh the session. This layout sits above [workspaceId], so
  // switching workspaces does not remount it and does not re-run this gate.
  useEffect(() => {
    let cancelled = false;
    let started = false;

    const runAuth = async () => {
      if (started) return;
      started = true;
      await useAuthStore.getState().checkAuth();
      if (!cancelled) setAuthReady(true);
    };

    const unsub = useAuthStore.persist.onFinishHydration(() => {
      void runAuth();
    });

    if (useAuthStore.persist.hasHydrated()) {
      void runAuth();
    }

    return () => {
      cancelled = true;
      unsub();
    };
  }, []);

  useEffect(() => {
    if (authReady && !token) {
      // Drop stale middleware cookie so /auth/login is not bounced back here.
      clearAuthFlagCookie();
      const redirect = pathname && pathname.startsWith('/') ? pathname : '/';
      router.replace(`/auth/login?redirect=${encodeURIComponent(redirect)}`);
    }
  }, [authReady, token, router, pathname]);

  useEffect(() => {
    if (!authReady || !token) return;
    let cancelled = false;
    void fetchWorkspaces().finally(() => {
      if (!cancelled) setMembershipChecked(true);
    });
    return () => {
      cancelled = true;
    };
  }, [authReady, token, fetchWorkspaces]);

  useEffect(() => {
    if (!membershipChecked || !token) return;
    if (workspaces.length === 0) {
      router.replace('/no-workspace');
    }
  }, [membershipChecked, token, workspaces.length, router]);

  const showShell = authReady && !!token;

  return (
    <WorkspaceErrorBoundary>
      <AsyncErrorCatcher />
      {/* `children` must appear in exactly ONE place in this tree. It used to be
          rendered here as well as inside the shell below, and because the two
          positions do not reconcile, React unmounted and remounted the entire
          page subtree the moment `showShell` flipped — every route fired all of
          its data fetches twice per load, the first time before auth was even
          ready. Render the spinner alone while the session is being checked. */}
      {!showShell ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: '#0a0a1a' }}>
          <div style={{ color: '#666', fontSize: 14 }}>Loading...</div>
        </div>
      ) : (
        <ShellTitleProvider>
          <WorkspaceLayout>{children}</WorkspaceLayout>
        </ShellTitleProvider>
      )}
    </WorkspaceErrorBoundary>
  );
}
