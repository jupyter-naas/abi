'use client';

import { useEffect, useMemo, useState, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import {
  LayoutGrid, Bot, Store, ArrowLeft, ExternalLink,
  Info, KeyRound, Copy, Check, Tag, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, OpenAppModule } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

interface AppInfo {
  module_path: string;
  module_name: string;
  app_name: string;
  app_id: string;
  category: string;
  name: string;
  description?: string;
  url?: string | null;
  avatar_url?: string | null;
  icon_emoji?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  maintainer?: string | null;
  tier?: string | null;
  installed: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-500',
  alpha:       'bg-amber-500/10 text-amber-600',
  ai:          'bg-blue-500/10 text-blue-500',
  core:        'bg-workspace-accent/10 text-workspace-accent',
};

function AppIcon({ app, size = 14 }: { app: Pick<AppInfo, 'avatar_url' | 'icon_emoji' | 'name'>; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (app.avatar_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={app.avatar_url}
        alt={app.name}
        style={{ width: size, height: size }}
        className="rounded object-cover flex-shrink-0"
        onError={() => setFailed(true)}
      />
    );
  }
  if (app.icon_emoji) {
    return (
      <span style={{ fontSize: size }} className="flex-shrink-0 leading-none">
        {app.icon_emoji}
      </span>
    );
  }
  return <Bot size={size} className="flex-shrink-0 text-workspace-accent" />;
}

function CopyButton({ value, secret }: { value: string; secret?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const handleCopy = () => {
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="flex items-center gap-1 border bg-muted/20 px-2 py-1 rounded">
      <span className={cn('flex-1 font-mono text-xs truncate', secret && !revealed && 'tracking-widest')}>
        {secret && !revealed ? '••••••••' : value}
      </span>
      {secret && (
        <button onClick={() => setRevealed(v => !v)} className="text-xs text-muted-foreground hover:text-foreground px-1">
          {revealed ? 'hide' : 'show'}
        </button>
      )}
      <button onClick={handleCopy} className="p-0.5 text-muted-foreground hover:text-foreground">
        {copied ? <Check size={11} className="text-emerald-500" /> : <Copy size={11} />}
      </button>
    </div>
  );
}

function AppDetailView({ mod, basePath }: { mod: OpenAppModule; basePath: string }) {
  const { setOpenAppModule } = useWorkspaceStore();
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Back */}
      <Link
        href={basePath}
        onClick={() => setOpenAppModule(null)}
        className="flex items-center gap-1.5 px-3 py-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors border-b border-border/50"
      >
        <ArrowLeft size={12} />
        <span>All apps</span>
      </Link>

      {/* Avatar + name */}
      <div className="flex flex-col items-center gap-2 px-4 py-5 border-b border-border/50 text-center">
        <AppIcon app={{ avatar_url: mod.logo_url, icon_emoji: null, name: mod.name }} size={40} />
        <div>
          <p className="font-semibold text-sm leading-tight">{mod.name}</p>
          <span className={cn('mt-1 inline-block px-2 py-0.5 text-xs font-medium rounded', CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground')}>
            <Tag size={9} className="mr-1 inline" />{mod.category}
          </span>
        </div>
      </div>

      <div className="p-3 space-y-4">
        {/* About */}
        {mod.description && (
          <div className="space-y-1">
            <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Info size={10} /> About
            </p>
            <p className="text-xs text-muted-foreground leading-relaxed">{mod.description}</p>
          </div>
        )}

        {/* Demo credentials */}
        {(mod.demo_login || mod.demo_password) && (
          <div className="border border-workspace-accent/20 bg-workspace-accent/5 p-2.5 space-y-2 rounded">
            <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-workspace-accent">
              <KeyRound size={10} /> Demo access
            </p>
            {mod.demo_login && (
              <div className="space-y-0.5">
                <p className="text-xs text-muted-foreground">Login</p>
                <CopyButton value={mod.demo_login} />
              </div>
            )}
            {mod.demo_password && (
              <div className="space-y-0.5">
                <p className="text-xs text-muted-foreground">Password</p>
                <CopyButton value={mod.demo_password} secret />
              </div>
            )}
          </div>
        )}

        {/* Meta */}
        {mod.maintainer && (
          <div className="space-y-0.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Maintainer</p>
            <p className="text-xs text-foreground">{mod.maintainer}</p>
          </div>
        )}

        {/* Module */}
        <div className="space-y-0.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Module</p>
          <p className="break-all font-mono text-xs text-muted-foreground">{mod.module_path}</p>
        </div>

        {/* Open in new tab */}
        {mod.app_url && (
          <a
            href={mod.app_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full items-center justify-center gap-1.5 py-2 text-xs font-semibold bg-workspace-accent text-white hover:bg-workspace-accent/90 transition-colors rounded"
          >
            <ExternalLink size={12} /> Open in new tab
          </a>
        )}
      </div>
    </div>
  );
}

function appToOpenModule(app: AppInfo): OpenAppModule {
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

// Group apps by their parent module_name (from backend). Returns sorted entries.
function groupAppsByModule(apps: AppInfo[]): Array<[string, AppInfo[]]> {
  const grouped = new Map<string, AppInfo[]>();
  for (const app of apps) {
    if (!grouped.has(app.module_name)) grouped.set(app.module_name, []);
    grouped.get(app.module_name)?.push(app);
  }
  return Array.from(grouped.entries()).sort(([a], [b]) =>
    a.localeCompare(b, undefined, { sensitivity: 'base' }),
  );
}

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId, setActivePanelSection, openAppModule } = useWorkspaceStore();
  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');
  const marketplacePath = getWorkspacePath(currentWorkspaceId, '/marketplace?type=applications');
  const pathname = usePathname();
  const isOnApps = pathname?.includes('/apps');

  const [apps, setApps] = useState<AppInfo[]>([]);
  const [panelLoading, setPanelLoading] = useState(true);
  const [expandedModules, setExpandedModules] = useState<string[]>([]);
  const [tooltip, setTooltip] = useState<{
    name: string;
    description: string;
    position: { top: number; left: number };
  } | null>(null);

  const showTooltip = (
    event: MouseEvent<HTMLAnchorElement>,
    name: string,
    description: string,
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({
      name,
      description,
      position: { top: rect.top, left: rect.right + 8 },
    });
  };
  const hideTooltip = () => setTooltip(null);

  useEffect(() => {
    const apiBase = getApiUrl();
    authFetch(`${apiBase}/api/apps/`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: { apps: AppInfo[] }) => {
        const installed = data.apps.filter((a) => a.installed && a.url);
        setApps(installed);
        // Expand all module groups by default
        setExpandedModules(Array.from(new Set(installed.map((a) => a.module_name))));
      })
      .catch(() => { /* fail silently */ })
      .finally(() => setPanelLoading(false));
  }, []);

  const groupedApps = useMemo(() => groupAppsByModule(apps), [apps]);
  const activeAppId = openAppModule
    ? `${openAppModule.module_path}:${openAppModule.app_url ?? ''}`
    : null;

  const toggleModule = (moduleName: string) => {
    setExpandedModules((prev) =>
      prev.includes(moduleName)
        ? prev.filter((m) => m !== moduleName)
        : [...prev, moduleName],
    );
  };

  const tooltipPortal = tooltip && typeof document !== 'undefined' && createPortal(
    <div
      className="fixed z-[100] max-w-xs rounded-md border border-border bg-popover px-3 py-2 text-sm shadow-lg animate-in fade-in-0 zoom-in-95 duration-100 pointer-events-none"
      style={{ top: tooltip.position.top, left: tooltip.position.left }}
    >
      <p className="font-medium">{tooltip.name}</p>
      {tooltip.description && (
        <p className="text-xs text-muted-foreground">{tooltip.description}</p>
      )}
    </div>,
    document.body,
  );

  // In detailOnly mode (SectionPanel), show the full dual-mode panel
  if (detailOnly) {
    if (panelLoading) {
      return (
        <div className="space-y-1 px-2 py-1">
          {[1, 2].map((i) => (
            <div key={i} className="h-7 w-full animate-pulse rounded-md bg-muted" />
          ))}
        </div>
      );
    }

    if (openAppModule) {
      return <AppDetailView mod={openAppModule} basePath={basePath} />;
    }

    return (
      <div className="space-y-0.5">
        {apps.length > 0 ? (
          <>
            <Link
              href={basePath}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                isOnApps && !openAppModule
                  ? 'bg-muted text-foreground font-medium'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <LayoutGrid size={14} />
              <span>Installed apps</span>
            </Link>
            {groupedApps.map(([moduleName, moduleApps]) => {
              const expanded = expandedModules.includes(moduleName);
              return (
                <div key={moduleName} className="space-y-0.5">
                  <button
                    onClick={() => toggleModule(moduleName)}
                    className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-xs font-medium text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-foreground"
                  >
                    <ChevronRight
                      size={10}
                      className={cn('flex-shrink-0 transition-transform', expanded && 'rotate-90')}
                    />
                    <span className="flex-1 truncate">{moduleName}</span>
                    <span className="text-[10px] text-muted-foreground">{moduleApps.length}</span>
                  </button>
                  {expanded && (
                    <div className="ml-4 space-y-0.5">
                      {moduleApps.map((app) => {
                        const isActive = activeAppId === `${app.module_path}:${app.url ?? ''}`;
                        return (
                          <Link
                            key={app.app_id}
                            href={`${basePath}?open=${encodeURIComponent(app.app_id)}`}
                            onClick={() => useWorkspaceStore.getState().setOpenAppModule(appToOpenModule(app))}
                            onMouseEnter={(e) => showTooltip(e, app.name, app.description || app.module_name)}
                            onMouseLeave={hideTooltip}
                            className={cn(
                              'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                              isActive
                                ? 'bg-muted text-foreground font-medium'
                                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                            )}
                          >
                            <AppIcon app={app} size={14} />
                            <span className="truncate">{app.name}</span>
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </>
        ) : (
          <Link
            href={basePath}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
              isOnApps && !openAppModule
                ? 'bg-muted text-foreground font-medium'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            <LayoutGrid size={14} />
            <span>Installed apps</span>
          </Link>
        )}

        <Link
          href={marketplacePath}
          onClick={() => setActivePanelSection('marketplace')}
          className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Store size={14} />
          <span>Browse Marketplace</span>
        </Link>
        {tooltipPortal}
      </div>
    );
  }

  // Full sidebar (non-panel) mode
  return (
    <CollapsibleSection
      id="apps"
      icon={<LayoutGrid size={18} />}
      label="Apps"
      description="Web apps from your installed modules"
      href={basePath}
      collapsed={collapsed}
    >
      {groupedApps.map(([moduleName, moduleApps]) => {
        const expanded = expandedModules.includes(moduleName);
        return (
          <div key={moduleName} className="space-y-0.5">
            <button
              onClick={() => toggleModule(moduleName)}
              className="flex w-full items-center gap-1 rounded-md px-2 py-1 text-left text-xs font-medium text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-foreground"
            >
              <ChevronRight
                size={10}
                className={cn('flex-shrink-0 transition-transform', expanded && 'rotate-90')}
              />
              <span className="flex-1 truncate">{moduleName}</span>
              <span className="text-[10px] text-muted-foreground">{moduleApps.length}</span>
            </button>
            {expanded && (
              <div className="ml-4 space-y-0.5">
                {moduleApps.map((app) => {
                  const isActive = activeAppId === `${app.module_path}:${app.url ?? ''}`;
                  return (
                    <Link
                      key={app.app_id}
                      href={`${basePath}?open=${encodeURIComponent(app.app_id)}`}
                      onMouseEnter={(e) => showTooltip(e, app.name, app.description || app.module_name)}
                      onMouseLeave={hideTooltip}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                        isActive
                          ? 'bg-muted text-foreground font-medium'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )}
                    >
                      <AppIcon app={app} size={14} />
                      <span className="truncate">{app.name}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
      {tooltipPortal}
    </CollapsibleSection>
  );
}
