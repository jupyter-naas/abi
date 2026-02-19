'use client';

import { Component, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { WorkspaceLayout } from '@/components/shell/workspace-layout';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import { useIntegrationsStore } from '@/stores/integrations';

// Catches unhandled promise rejections (not caught by React error boundaries)
function AsyncErrorCatcher() {
  const [asyncError, setAsyncError] = useState<string | null>(null);

  useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const msg = event.reason?.message || event.reason?.toString() || 'Unknown async error';
      const stack = event.reason?.stack || '';
      console.error('[NEXUS Unhandled Rejection]', msg, stack);
      setAsyncError(`${msg}\n\n${stack}`);
      event.preventDefault();
    };

    const handleError = (event: ErrorEvent) => {
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
      );
    }
    return this.props.children;
  }
}

export default function WorkspaceIdLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  
  const { workspaces, currentWorkspaceId, setCurrentWorkspace } = useWorkspaceStore();
  const { isAuthenticated, token } = useAuthStore();
  const [authReady, setAuthReady] = useState(false);

  // Wait for auth store to rehydrate from localStorage before doing anything
  useEffect(() => {
    // Zustand persist rehydrates synchronously on first render in most cases,
    // but we add a small delay to be safe
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      setAuthReady(true);
    });
    // If already hydrated (e.g., navigating between pages)
    if (useAuthStore.persist.hasHydrated()) {
      setAuthReady(true);
    }
    return unsub;
  }, []);

  // Redirect to login if not authenticated (after hydration)
  useEffect(() => {
    if (authReady && !token) {
      router.replace(`/auth/login?redirect=/workspace/${workspaceId}/chat`);
    }
  }, [authReady, token, router, workspaceId]);

  // Sync URL workspaceId with store
  useEffect(() => {
    if (workspaceId && workspaceId !== currentWorkspaceId) {
      // Check if workspace exists
      const workspace = workspaces.find(w => w.id === workspaceId);
      if (workspace) {
        setCurrentWorkspace(workspaceId);
      } else if (workspaces.length > 0) {
        // Redirect to first workspace if not found
        router.replace(`/workspace/${workspaces[0].id}/chat`);
      }
    }
  }, [workspaceId, currentWorkspaceId, workspaces, setCurrentWorkspace, router]);

  // Refresh providers (OpenRouter, etc.) when workspace loads — syncs with secrets
  useEffect(() => {
    if (authReady && token && currentWorkspaceId) {
      useIntegrationsStore.getState().refreshProviders();
    }
  }, [authReady, token, currentWorkspaceId]);

  // Show nothing while checking auth
  if (!authReady || !token) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: '#0a0a1a' }}>
        <div style={{ color: '#666', fontSize: 14 }}>Loading...</div>
      </div>
    );
  }

  return (
    <WorkspaceErrorBoundary>
      <AsyncErrorCatcher />
      <WorkspaceLayout>{children}</WorkspaceLayout>
    </WorkspaceErrorBoundary>
  );
}
