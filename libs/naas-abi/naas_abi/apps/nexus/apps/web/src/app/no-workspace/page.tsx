'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { FolderKanban, Loader2, LogOut } from 'lucide-react';
import { clearAuthFlagCookie } from '@/lib/auth-session';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';

function slugify(value: string): string {
  const base = value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
  return base.length >= 2 ? base : `workspace-${Date.now().toString(36)}`;
}

export default function NoWorkspacePage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const logout = useAuthStore((s) => s.logout);
  const fetchWorkspaces = useWorkspaceStore((s) => s.fetchWorkspaces);
  const workspaces = useWorkspaceStore((s) => s.workspaces);

  const [authReady, setAuthReady] = useState(false);
  const [checking, setChecking] = useState(true);
  const [name, setName] = useState('');
  const [nameTouched, setNameTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const suggestedSlug = useMemo(() => slugify(name || 'my-workspace'), [name]);

  useEffect(() => {
    let cancelled = false;
    const boot = async () => {
      await useAuthStore.getState().checkAuth();
      if (!cancelled) setAuthReady(true);
    };
    if (useAuthStore.persist.hasHydrated()) {
      void boot();
    }
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      void boot();
    });
    return () => {
      cancelled = true;
      unsub();
    };
  }, []);

  useEffect(() => {
    if (nameTouched || name.trim()) return;
    const suggested = user?.name?.trim();
    if (suggested) setName(suggested);
  }, [user?.name, name, nameTouched]);

  useEffect(() => {
    if (!authReady) return;
    if (!token) {
      clearAuthFlagCookie();
      router.replace('/auth/login');
      return;
    }
    let cancelled = false;
    void fetchWorkspaces().finally(() => {
      if (!cancelled) setChecking(false);
    });
    return () => {
      cancelled = true;
    };
  }, [authReady, token, fetchWorkspaces, router]);

  useEffect(() => {
    if (checking || workspaces.length === 0) return;
    router.replace(`/workspace/${workspaces[0].id}/chat`);
  }, [checking, workspaces, router]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Enter a workspace name');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await authFetch('/api/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: trimmed,
          slug: slugify(trimmed),
        }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Could not create workspace');
      }
      const created = await response.json();
      await fetchWorkspaces();
      router.replace(`/workspace/${created.id}/chat`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create workspace');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSignOut = () => {
    logout();
    clearAuthFlagCookie();
    router.replace('/auth/login');
  };

  if (!authReady || checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Checking workspace access...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-sm">
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <FolderKanban size={24} />
        </div>
        <h1 className="text-xl font-semibold tracking-tight">No workspace yet</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          You are signed in{user?.email ? ` as ${user.email}` : ''}, but you are not a member of any
          workspace. Ask an organization admin to invite you, or create one below.
        </p>

        <form onSubmit={handleCreate} className="mt-6 space-y-3">
          <label className="block text-sm font-medium" htmlFor="workspace-name">
            Workspace name
          </label>
          <input
            id="workspace-name"
            value={name}
            onChange={(e) => {
              setNameTouched(true);
              setName(e.target.value);
            }}
            placeholder={user?.name?.trim() || 'My workspace'}
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            disabled={submitting}
            autoFocus
          />
          <p className="text-xs text-muted-foreground">Slug: {suggestedSlug}</p>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Create workspace
          </button>
        </form>

        <p className="mt-4 text-xs text-muted-foreground">
          Any signed-in user can create a personal workspace via the API. Organization settings
          Create Workspace buttons still require an org admin workflow and are not wired for members.
        </p>

        <button
          type="button"
          onClick={handleSignOut}
          className="mt-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <LogOut size={14} />
          Sign out
        </button>
      </div>
    </div>
  );
}
