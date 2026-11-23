'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, Loader2, LogOut } from 'lucide-react';
import { useTenant } from '@/contexts/tenant-context';
import { clearAuthFlagCookie } from '@/lib/auth-session';
import { authFetch, selectSession, useAuthStore } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';

function isLightColor(hex: string): boolean {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.6;
}

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
  const tenant = useTenant();
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore(selectSession);
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

  // The login page's look (auth/login/login-form.tsx), from the same tenant branding.
  const primaryColor = tenant.primary_color || '#34D399';
  const accentColor = tenant.accent_color || '#1FA574';
  const bgColor = tenant.background_color || '#FFFFFF';
  const cardColor = tenant.login_card_color || '#FFFFFF';
  const radius = `${tenant.login_border_radius || '0'}px`;
  const cardIsLight = isLightColor(cardColor);
  const textColor = tenant.login_text_color || (cardIsLight ? '#1a1a1a' : '#ffffff');
  const mutedTextColor = cardIsLight ? 'rgba(0,0,0,0.55)' : 'rgba(255,255,255,0.55)';
  const subtitleColor = cardIsLight ? 'rgba(0,0,0,0.45)' : 'rgba(255,255,255,0.45)';
  const logoUrl = tenant.logo_rectangle_url || tenant.logo_url;

  if (!authReady || checking) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ backgroundColor: bgColor, fontFamily: tenant.font_family || undefined }}
      >
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin" style={{ color: primaryColor }} />
          <p className="text-sm" style={{ color: mutedTextColor }}>
            Checking workspace access...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4"
      style={{ backgroundColor: bgColor, fontFamily: tenant.font_family || undefined }}
    >
      {tenant.font_url && <link rel="stylesheet" href={tenant.font_url} />}
      <div
        className="w-full"
        style={{
          maxWidth: tenant.login_card_max_width || '440px',
          padding: tenant.login_card_padding || '2.5rem 3rem 3rem',
          backgroundColor: cardColor,
          borderRadius: radius,
          color: textColor,
        }}
      >
        {logoUrl && (
          <div className="mb-6 flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={logoUrl} alt={tenant.tab_title} className="h-12 max-w-full object-contain" />
          </div>
        )}
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold leading-tight">No workspace yet</h1>
          <p className="mt-2 text-sm" style={{ color: mutedTextColor }}>
            You are signed in{user?.email ? ` as ${user.email}` : ''}, but you are not a member of
            any workspace. Ask an organization admin to invite you, or create one below.
          </p>
        </div>

        {error && (
          <div
            className="mb-6 flex items-center gap-2 bg-destructive/10 p-3 text-sm text-destructive"
            style={{ borderRadius: radius }}
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleCreate} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="workspace-name" className="text-sm font-medium">
              Workspace name
            </label>
            <input
              id="workspace-name"
              value={name}
              onChange={(e) => {
                setNameTouched(true);
                setName(e.target.value);
                if (error) setError(null);
              }}
              placeholder={user?.name?.trim() || 'My workspace'}
              className="flex h-11 w-full px-4 py-2 text-sm focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50"
              style={{
                borderRadius: radius,
                backgroundColor: tenant.login_input_color || '#F4F4F4',
                border: 'none',
                color: textColor,
                '--tw-ring-color': `${accentColor}33`,
              } as React.CSSProperties}
              disabled={submitting}
              autoFocus
            />
            <p className="text-xs" style={{ color: subtitleColor }}>
              Slug: {suggestedSlug}
            </p>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="flex h-11 w-full items-center justify-center gap-2 px-4 text-sm font-medium text-white transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60"
            style={{
              backgroundColor: primaryColor,
              borderRadius: radius,
              '--tw-ring-color': primaryColor,
            } as React.CSSProperties}
            onMouseEnter={(e) => {
              if (!submitting) e.currentTarget.style.backgroundColor = accentColor;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = primaryColor;
            }}
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Create workspace
          </button>
        </form>

        <button
          type="button"
          onClick={handleSignOut}
          className="mt-6 flex h-11 w-full items-center justify-center gap-2 px-4 text-sm font-medium transition-all"
          style={{ borderRadius: radius, border: `1px solid ${mutedTextColor}`, color: textColor }}
        >
          <LogOut size={14} />
          Sign out
        </button>
      </div>
      {tenant.login_footer_text && (
        <p className="mt-8 text-center text-caption" style={{ color: subtitleColor }}>
          {tenant.login_footer_text}
        </p>
      )}
    </div>
  );
}
