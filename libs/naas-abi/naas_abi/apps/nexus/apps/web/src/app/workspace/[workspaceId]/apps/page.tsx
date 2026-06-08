'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AppWindow, Bot, ExternalLink, Search, Globe,
  ChevronLeft, ChevronRight, RefreshCw, AlertTriangle,
  Tag, Info, KeyRound, Copy, Check, PanelLeft, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import Link from 'next/link';
import { useWorkspaceStore } from '@/stores/workspace';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AppInfo {
  module_path: string;
  app_name: string;
  app_id: string;
  category: string;
  name: string;
  description: string;
  url?: string | null;
  avatar_url?: string | null;
  icon_emoji?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  version?: string | null;
  author?: string | null;
  license?: string | null;
  keywords?: string[];
  tier?: string | null;
  maintainer?: string | null;
  installed: boolean;
  enabled: boolean;
}

interface AppsResponse {
  apps: AppInfo[];
}

type TenantApp = {
  name: string;
  url: string;
  description?: string | null;
  icon_emoji?: string | null;
};

// Unified app entry used in the embed view
type AppEntry =
  | { kind: 'app'; data: AppInfo; url: string }
  | { kind: 'tenant'; data: TenantApp };

function appEntryUrl(entry: AppEntry): string {
  return entry.kind === 'app' ? entry.url : entry.data.url;
}
function appEntryName(entry: AppEntry): string {
  return entry.data.name;
}
function appEntryDescription(entry: AppEntry): string | null {
  return entry.kind === 'app' ? entry.data.description : (entry.data.description ?? null);
}

// Translate AppInfo → the shared OpenAppModule shape consumed by the sidebar.
function appInfoToOpenModule(app: AppInfo) {
  return {
    module_path: app.module_path,
    name: app.name,
    description: app.description,
    logo_url: app.avatar_url ?? null,
    category: app.category,
    app_url: app.url ?? null,
    demo_login: app.demo_login ?? null,
    demo_password: app.demo_password ?? null,
    maintainer: app.maintainer ?? null,
    tier: app.tier ?? null,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-500',
  alpha: 'bg-amber-500/10 text-amber-600',
  ai: 'bg-blue-500/10 text-blue-500',
  domain: 'bg-amber-500/10 text-amber-600',
  core: 'bg-workspace-accent/10 text-workspace-accent',
};

// ---------------------------------------------------------------------------
// Module avatar
// ---------------------------------------------------------------------------

function AppAvatar({ app, size = 'md' }: { app: AppInfo; size?: 'sm' | 'md' | 'lg' }) {
  const [failed, setFailed] = useState(false);
  const dims = size === 'lg' ? 'h-16 w-16' : size === 'sm' ? 'h-8 w-8' : 'h-12 w-12';
  const iconSize = size === 'lg' ? 32 : size === 'sm' ? 16 : 24;
  const emojiSize = size === 'lg' ? 'text-3xl' : size === 'sm' ? 'text-base' : 'text-2xl';

  if (app.avatar_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={app.avatar_url}
        alt={app.name}
        className={cn(dims, 'rounded-lg object-cover flex-shrink-0')}
        onError={() => setFailed(true)}
      />
    );
  }
  if (app.icon_emoji) {
    return (
      <div className={cn(dims, emojiSize, 'flex flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10')}>
        {app.icon_emoji}
      </div>
    );
  }
  return (
    <div className={cn(dims, 'flex flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10')}>
      <Bot size={iconSize} className="text-workspace-accent" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// App card (grid view)
// ---------------------------------------------------------------------------

function AppCard({ entry, onSelect }: { entry: AppEntry; onSelect: () => void }) {
  const name = appEntryName(entry);
  const description = appEntryDescription(entry);
  const url = appEntryUrl(entry);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      className="glass-card flex flex-col gap-4 p-5 cursor-pointer transition-all hover:border-workspace-accent/40 hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-workspace-accent/40"
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        {entry.kind === 'app' ? (
          <AppAvatar app={entry.data} />
        ) : (
          <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10 text-2xl">
            {entry.data.icon_emoji ?? <Globe size={24} className="text-workspace-accent" />}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold leading-tight truncate">{name}</h3>
          {entry.kind === 'app' ? (
            <span className={cn('mt-1 inline-block px-2 py-0.5 text-xs font-medium', CATEGORY_COLORS[entry.data.category] ?? 'bg-muted text-muted-foreground')}>
              {entry.data.category}
            </span>
          ) : (
            <span className="mt-1 inline-block px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">External</span>
          )}
        </div>
      </div>

      {/* Description */}
      {description && (
        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2 flex-1">{description}</p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
        {entry.kind === 'app' ? (
          <span className="text-xs text-muted-foreground truncate max-w-[140px]">
            {entry.data.maintainer ?? entry.data.category}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground truncate max-w-[140px]">{url}</span>
        )}
        <span className="flex items-center gap-1 px-3 py-1 text-xs font-semibold bg-workspace-accent/10 text-workspace-accent transition-colors group-hover:bg-workspace-accent group-hover:text-white">
          <AppWindow size={11} /> Open
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Copy-to-clipboard field
// ---------------------------------------------------------------------------

function CopyField({ label, value, secret }: { label: string; value: string; secret?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const display = secret && !revealed ? '••••••••' : value;

  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground font-medium">{label}</p>
      <div className="flex items-center gap-1 border bg-muted/20 px-2 py-1.5">
        <span
          className={cn('flex-1 font-mono text-xs text-foreground truncate', secret && !revealed && 'tracking-widest')}
        >
          {display}
        </span>
        {secret && (
          <button
            onClick={() => setRevealed((v) => !v)}
            className="px-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {revealed ? 'hide' : 'show'}
          </button>
        )}
        <button
          onClick={handleCopy}
          title="Copy"
          className="p-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail panel (sidebar inside embed view)
// ---------------------------------------------------------------------------

function AppDetailPanel({
  entry,
  apps,
  collapsed,
  onToggle,
  onSwitch,
}: {
  entry: AppEntry;
  apps: AppInfo[];
  collapsed: boolean;
  onToggle: () => void;
  onSwitch: (app: AppInfo) => void;
}) {
  const name = appEntryName(entry);
  const description = appEntryDescription(entry);
  const url = appEntryUrl(entry);
  const activeAppId = entry.kind === 'app' ? entry.data.app_id : null;

  return (
    <div className={cn('flex flex-col border-r border-border/50 bg-background transition-all duration-300 flex-shrink-0', collapsed ? 'w-10' : 'w-64')}>
      {/* Toggle strip */}
      <button
        onClick={onToggle}
        title={collapsed ? 'Expand details' : 'Collapse details'}
        className="flex h-10 w-full flex-shrink-0 items-center justify-center border-b border-border/50 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>

      {/* Panel content */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto">
          {/* App switcher nav */}
          {apps.length > 1 && (
            <div className="border-b border-border/50 p-2 space-y-0.5">
              {apps.map((app) => {
                const isActive = app.app_id === activeAppId;
                return (
                  <button
                    key={app.app_id}
                    onClick={() => onSwitch(app)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors text-left',
                      isActive
                        ? 'bg-muted text-foreground font-medium'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )}
                  >
                    <AppAvatar app={app} size="sm" />
                    <span className="truncate">{app.name}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Avatar + name */}
          <div className="flex flex-col items-center gap-3 px-4 py-6 border-b border-border/50 text-center">
            {entry.kind === 'app' ? (
              <AppAvatar app={entry.data} size="lg" />
            ) : (
              <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10 text-3xl">
                {entry.data.icon_emoji ?? <Globe size={32} className="text-workspace-accent" />}
              </div>
            )}
            <div>
              <h2 className="font-bold text-base leading-tight">{name}</h2>
              {entry.kind === 'app' && (
                <span className={cn('mt-1.5 inline-block px-2 py-0.5 text-xs font-medium', CATEGORY_COLORS[entry.data.category] ?? 'bg-muted text-muted-foreground')}>
                  <Tag size={9} className="mr-1 inline" />
                  {entry.data.category}
                </span>
              )}
            </div>
          </div>

          <div className="space-y-4 p-4">
            {/* Description */}
            {description && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                  <Info size={11} /> About
                </p>
                <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
              </div>
            )}

            {/* Demo credentials */}
            {entry.kind === 'app' && (entry.data.demo_login || entry.data.demo_password) && (
              <div className="border border-workspace-accent/20 bg-workspace-accent/5 p-3 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-workspace-accent flex items-center gap-1.5">
                  <KeyRound size={11} /> Demo access
                </p>
                {entry.data.demo_login && (
                  <CopyField label="Login" value={entry.data.demo_login} />
                )}
                {entry.data.demo_password && (
                  <CopyField label="Password" value={entry.data.demo_password} secret />
                )}
              </div>
            )}

            {/* App details */}
            {entry.kind === 'app' && (
              <>
                {entry.data.maintainer && (
                  <div className="border bg-muted/30 p-3 space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Maintainer</p>
                    <p className="text-sm text-foreground">{entry.data.maintainer}</p>
                  </div>
                )}
                {entry.data.tier && (
                  <div className="border bg-muted/30 p-3 space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tier</p>
                    <p className="text-sm text-foreground capitalize">{entry.data.tier}</p>
                  </div>
                )}
                <div className="border bg-muted/30 p-3 space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Module</p>
                  <p className="break-all font-mono text-xs text-muted-foreground">{entry.data.module_path}</p>
                </div>
              </>
            )}

            {/* URL */}
            <div className="border bg-muted/30 p-3 space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">URL</p>
              <p className="break-all font-mono text-xs text-muted-foreground">{url}</p>
            </div>

            {/* Open in new tab */}
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex w-full items-center justify-center gap-2 py-2.5 text-sm font-semibold bg-workspace-accent text-white hover:bg-workspace-accent/90 transition-colors"
            >
              <ExternalLink size={14} />
              Open in new tab
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Embed view
// ---------------------------------------------------------------------------

function EmbedView({ entry, onBack }: { entry: AppEntry; onBack: () => void }) {
  const url = appEntryUrl(entry);
  const name = appEntryName(entry);
  const [blocked, setBlocked] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { activePanelSection, setActivePanelSection } = useWorkspaceStore();

  // Detect X-Frame-Options block: the iframe will fire onLoad with an empty
  // document when blocked. We use a timeout heuristic — if the iframe loads
  // instantly (<100 ms) without a cross-origin document, it was likely blocked.
  const loadStartRef = useRef(Date.now());

  const handleLoad = () => {
    const elapsed = Date.now() - loadStartRef.current;
    // A blocked iframe loads near-instantly with an empty body
    if (elapsed < 80) {
      setBlocked(true);
    }
  };

  const handleReload = () => {
    loadStartRef.current = Date.now();
    setBlocked(false);
    setReloadKey((k) => k + 1);
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex h-12 flex-shrink-0 items-center gap-2 border-b border-border/50 px-3 bg-background">
        <button
          onClick={() => setActivePanelSection(activePanelSection === 'apps' ? null : 'apps')}
          title={activePanelSection === 'apps' ? 'Close panel' : 'Open panel'}
          className={cn(
            'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded transition-colors',
            activePanelSection === 'apps'
              ? 'bg-muted text-foreground'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
          )}
        >
          <PanelLeft size={15} />
        </button>
        <span className="text-sm font-medium truncate flex-1">{name}</span>
        <button
          onClick={handleReload}
          title="Reload"
          className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground rounded transition-colors"
        >
          <RefreshCw size={13} />
        </button>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          title="Open in new tab"
          className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground rounded transition-colors"
        >
          <ExternalLink size={13} />
        </a>
        <button
          onClick={onBack}
          title="Close app"
          className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground rounded transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body: full-width iframe — detail is in the left section panel */}
      <div className="relative flex-1 overflow-hidden bg-muted/20">
          {blocked ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center p-8">
              <AlertTriangle size={36} className="text-amber-500" />
              <div>
                <p className="font-semibold text-foreground">Embedding blocked</p>
                <p className="mt-1 text-sm text-muted-foreground max-w-xs">
                  This site has disabled embedding via <code className="text-xs bg-muted px-1 py-0.5 rounded">X-Frame-Options</code>. Open it in a new tab instead.
                </p>
              </div>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-workspace-accent text-white hover:bg-workspace-accent/90 transition-colors"
              >
                <ExternalLink size={14} />
                Open {name}
              </a>
            </div>
          ) : (
            <iframe
              key={reloadKey}
              ref={iframeRef}
              src={url}
              title={name}
              onLoad={handleLoad}
              onLoadStart={() => { loadStartRef.current = Date.now(); }}
              className="h-full w-full border-0"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-presentation"
              allow="fullscreen"
            />
          )}
        </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState({ hasSearch, workspaceId }: { hasSearch: boolean; workspaceId: string }) {
  if (hasSearch) {
    return <p className="py-16 text-center text-sm text-muted-foreground">No apps match your search.</p>;
  }
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <AppWindow size={40} className="text-muted-foreground/30" />
      <div>
        <p className="font-medium text-foreground">No apps installed yet</p>
        <p className="mt-1 text-sm text-muted-foreground max-w-sm">
          Install modules from the Marketplace to see their apps here.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AppsPage() {
  const tenant = useTenant();
  const { currentWorkspaceId, setOpenAppModule, setActivePanelSection } = useWorkspaceStore();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [search, setSearch] = useState('');
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeApp, setActiveApp] = useState<AppEntry | null>(null);

  useEffect(() => {
    return () => { setOpenAppModule(null); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Restore last opened app when navigating back to the section without ?open=
  useEffect(() => {
    if (!currentWorkspaceId) return;
    if (searchParams?.get('open')) return;
    try {
      const saved = sessionStorage.getItem(`nexus.apps.last_open.${currentWorkspaceId}`);
      if (saved) {
        router.replace(`/workspace/${currentWorkspaceId}/apps?open=${encodeURIComponent(saved)}`);
      }
    } catch {
      // sessionStorage unavailable (e.g. private mode restrictions) — ignore
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspaceId]);

  useEffect(() => {
    const apiBase = getApiUrl();
    if (!currentWorkspaceId) return;
    setLoading(true);
    authFetch(`${apiBase}/api/apps/?workspace_id=${encodeURIComponent(currentWorkspaceId)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: AppsResponse) => {
        setApps(data.apps.filter((a) => a.installed && a.url && a.enabled));
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentWorkspaceId]);

  // Sync activeApp with ?open= so navigating back to the gallery (without the
  // query param) clears the embed view.
  useEffect(() => {
    const openParam = searchParams?.get('open');
    if (!openParam) {
      setActiveApp(null);
      setOpenAppModule(null);
      return;
    }
    const app =
      apps.find((a) => a.app_id === openParam) ??
      apps.find((a) => a.module_path === openParam);
    if (app?.url) {
      setActiveApp({ kind: 'app', data: app, url: app.url });
      setOpenAppModule(appInfoToOpenModule(app));
      setActivePanelSection('apps');
      return;
    }
    const tenantApp = tenant.apps.find((a) => a.url === openParam);
    if (tenantApp) {
      setActiveApp({ kind: 'tenant', data: tenantApp });
      setOpenAppModule(null);
      setActivePanelSection('apps');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, apps, tenant.apps]);

  const lastOpenKey = currentWorkspaceId ? `nexus.apps.last_open.${currentWorkspaceId}` : null;

  const handleClose = () => {
    setActiveApp(null);
    setOpenAppModule(null);
    if (lastOpenKey) sessionStorage.removeItem(lastOpenKey);
    const base = `/workspace/${currentWorkspaceId}/apps`;
    router.replace(base);
  };

  const handleOpen = (entry: AppEntry) => {
    setActiveApp(entry);
    if (entry.kind === 'app') setOpenAppModule(appInfoToOpenModule(entry.data));
    else setOpenAppModule(null);
    setActivePanelSection('apps');
    const param = entry.kind === 'app' ? entry.data.app_id : entry.data.url;
    if (lastOpenKey) sessionStorage.setItem(lastOpenKey, param);
    const base = `/workspace/${currentWorkspaceId}/apps`;
    router.replace(`${base}?open=${encodeURIComponent(param)}`);
  };

  const filteredApps = useMemo(() => {
    if (!search) return apps;
    const q = search.toLowerCase();
    return apps.filter((a) => a.name.toLowerCase().includes(q) || a.description?.toLowerCase().includes(q));
  }, [apps, search]);

  const filteredTenantApps = useMemo(() => {
    if (!search) return tenant.apps;
    const q = search.toLowerCase();
    return tenant.apps.filter((a) => a.name.toLowerCase().includes(q) || (a.description ?? '').toLowerCase().includes(q));
  }, [tenant.apps, search]);

  const totalCount = filteredApps.length + filteredTenantApps.length;
  const isEmpty = !loading && !error && totalCount === 0;

  // Embed view: replaces the entire page body
  if (activeApp) {
    return (
      <div className="flex h-full flex-col">
        <EmbedView entry={activeApp} onBack={handleClose} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <Header title="Apps" subtitle="Your installed and configured apps" />

      <div className="flex-1 overflow-auto">
        <div className="p-6 space-y-6">

          {/* Toolbar */}
          <div className="flex items-center gap-4">
            <div className="relative max-w-md flex-1">
              <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search apps..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-10 w-full border bg-background pl-10 pr-4 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
          </div>

          {/* States */}
          {loading && (
            <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
              <AppWindow size={18} className="mr-2 animate-pulse" /> Loading apps...
            </div>
          )}
          {error && (
            <div className="border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load: {error}
            </div>
          )}
          {isEmpty && <EmptyState hasSearch={!!search} workspaceId={currentWorkspaceId ?? ''} />}

          {/* Tenant apps */}
          {!loading && !error && filteredTenantApps.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">External</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredTenantApps.map((app) => (
                  <AppCard
                    key={app.url}
                    entry={{ kind: 'tenant', data: app }}
                    onSelect={() => handleOpen({ kind: 'tenant', data: app })}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Module apps */}
          {!loading && !error && filteredApps.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Apps</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredApps.map((app) => {
                  const url = app.url ?? '';
                  if (!url) return null;
                  return (
                    <AppCard
                      key={app.app_id}
                      entry={{ kind: 'app', data: app, url }}
                      onSelect={() => handleOpen({ kind: 'app', data: app, url })}
                    />
                  );
                })}
              </div>
            </section>
          )}

        </div>
      </div>
    </div>
  );
}
