'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AppWindow, Bot, ExternalLink, Search, Globe,
  ArrowLeft, ChevronLeft, ChevronRight, RefreshCw, AlertTriangle,
  Tag, Info, KeyRound, Copy, Check,
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

interface ModuleInfo {
  module_path: string;
  name: string;
  description: string;
  logo_url: string | null;
  category: string;
  installed: boolean;
  app_url?: string | null;
  maintainer?: string | null;
  tier?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
}

interface ModulesResponse {
  installed: ModuleInfo[];
  available: ModuleInfo[];
}

type TenantApp = {
  name: string;
  url: string;
  description?: string | null;
  icon_emoji?: string | null;
};

// Unified app entry used in the embed view
type AppEntry =
  | { kind: 'module'; data: ModuleInfo; url: string }
  | { kind: 'tenant'; data: TenantApp };

function appEntryUrl(entry: AppEntry): string {
  return entry.kind === 'module' ? entry.url : entry.data.url;
}
function appEntryName(entry: AppEntry): string {
  return entry.kind === 'module' ? entry.data.name : entry.data.name;
}
function appEntryDescription(entry: AppEntry): string | null {
  return entry.kind === 'module' ? entry.data.description : (entry.data.description ?? null);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

import { APP_CATEGORIES, hasApp } from '@/lib/app-constants';

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

function ModuleAvatar({ mod, size = 'md' }: { mod: ModuleInfo; size?: 'sm' | 'md' | 'lg' }) {
  const [failed, setFailed] = useState(false);
  const dims = size === 'lg' ? 'h-16 w-16' : size === 'sm' ? 'h-8 w-8' : 'h-12 w-12';
  const iconSize = size === 'lg' ? 32 : size === 'sm' ? 16 : 24;

  if (mod.logo_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={mod.logo_url}
        alt={mod.name}
        className={cn(dims, 'rounded-lg object-cover flex-shrink-0')}
        onError={() => setFailed(true)}
      />
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
        {entry.kind === 'module' ? (
          <ModuleAvatar mod={entry.data} />
        ) : (
          <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10 text-2xl">
            {entry.data.icon_emoji ?? <Globe size={24} className="text-workspace-accent" />}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold leading-tight truncate">{name}</h3>
          {entry.kind === 'module' ? (
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
        {entry.kind === 'module' ? (
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
  collapsed,
  onToggle,
}: {
  entry: AppEntry;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const name = appEntryName(entry);
  const description = appEntryDescription(entry);
  const url = appEntryUrl(entry);

  return (
    <div className={cn('flex flex-col border-r border-border/50 bg-background transition-all duration-300 flex-shrink-0', collapsed ? 'w-10' : 'w-72')}>
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
          {/* Avatar + name */}
          <div className="flex flex-col items-center gap-3 px-4 py-6 border-b border-border/50 text-center">
            {entry.kind === 'module' ? (
              <ModuleAvatar mod={entry.data} size="lg" />
            ) : (
              <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-lg bg-workspace-accent/10 text-3xl">
                {entry.data.icon_emoji ?? <Globe size={32} className="text-workspace-accent" />}
              </div>
            )}
            <div>
              <h2 className="font-bold text-base leading-tight">{name}</h2>
              {entry.kind === 'module' && (
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
            {entry.kind === 'module' && (entry.data.demo_login || entry.data.demo_password) && (
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

            {/* Module details */}
            {entry.kind === 'module' && (
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
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);

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
      <div className="flex h-12 flex-shrink-0 items-center gap-3 border-b border-border/50 px-4 bg-background">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft size={15} />
          <span className="hidden sm:inline">Apps</span>
        </button>
        <div className="h-4 w-px bg-border" />
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
      </div>

      {/* Body: detail panel + iframe */}
      <div className="flex flex-1 overflow-hidden">
        <AppDetailPanel
          entry={entry}
          collapsed={panelCollapsed}
          onToggle={() => setPanelCollapsed((v) => !v)}
        />

        {/* Iframe area */}
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
      <Link
        href={`/workspace/${workspaceId}/marketplace?type=applications`}
        className="mt-2 px-4 py-2 text-sm font-semibold bg-workspace-accent text-white hover:bg-workspace-accent/90 transition-colors"
      >
        Browse Marketplace
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AppsPage() {
  const tenant = useTenant();
  const { currentWorkspaceId } = useWorkspaceStore();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [search, setSearch] = useState('');
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeApp, setActiveApp] = useState<AppEntry | null>(null);

  useEffect(() => {
    const apiBase = getApiUrl();
    setLoading(true);
    authFetch(`${apiBase}/api/modules/`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: ModulesResponse) => {
        const map = new Map<string, ModuleInfo>();
        for (const m of data.available) map.set(m.module_path, m);
        for (const m of data.installed) map.set(m.module_path, { ...map.get(m.module_path) ?? m, installed: true });
        const installed = Array.from(map.values()).filter((m) => m.installed && hasApp(m));
        setModules(installed);

        // Auto-open from ?open= deep-link
        const openParam = searchParams?.get('open');
        if (openParam) {
          const mod = installed.find((m) => m.module_path === openParam);
          if (mod?.app_url) {
            setActiveApp({ kind: 'module', data: mod, url: mod.app_url });
          } else {
            // Try tenant apps by URL
            const tenantApp = tenant.apps.find((a) => a.url === openParam);
            if (tenantApp) setActiveApp({ kind: 'tenant', data: tenantApp });
          }
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleClose = () => {
    setActiveApp(null);
    // Clear the ?open param without pushing a new history entry
    const base = `/workspace/${currentWorkspaceId}/apps`;
    router.replace(base);
  };

  const handleOpen = (entry: AppEntry) => {
    setActiveApp(entry);
    const param = entry.kind === 'module'
      ? entry.data.module_path
      : entry.data.url;
    const base = `/workspace/${currentWorkspaceId}/apps`;
    router.replace(`${base}?open=${encodeURIComponent(param)}`);
  };

  const filteredModules = useMemo(() => {
    if (!search) return modules;
    const q = search.toLowerCase();
    return modules.filter((m) => m.name.toLowerCase().includes(q) || m.description?.toLowerCase().includes(q));
  }, [modules, search]);

  const filteredTenantApps = useMemo(() => {
    if (!search) return tenant.apps;
    const q = search.toLowerCase();
    return tenant.apps.filter((a) => a.name.toLowerCase().includes(q) || (a.description ?? '').toLowerCase().includes(q));
  }, [tenant.apps, search]);

  const totalCount = filteredModules.length + filteredTenantApps.length;
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
            <Link
              href={`/workspace/${currentWorkspaceId}/marketplace?type=applications`}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <ExternalLink size={12} />
              Browse Marketplace
            </Link>
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
          {!loading && !error && filteredModules.length > 0 && (
            <section>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">Apps</h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {filteredModules.map((mod) => {
                  const url = mod.app_url ?? '';
                  if (!url) return null;
                  return (
                    <AppCard
                      key={mod.module_path}
                      entry={{ kind: 'module', data: mod, url }}
                      onSelect={() => handleOpen({ kind: 'module', data: mod, url })}
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
