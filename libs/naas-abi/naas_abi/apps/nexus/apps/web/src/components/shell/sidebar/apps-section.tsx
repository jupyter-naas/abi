'use client';

import { useEffect, useMemo, useState, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import {
  LayoutGrid, ArrowLeft, ExternalLink, Info, KeyRound, Copy, Check, Tag,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, OpenAppModule } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';
import { AppIcon } from '@/app/workspace/[workspaceId]/apps/components/primitives';
import {
  recordToOpenModule, toRecord, toTenantRecord,
  type AppRecord, type AppsResponse,
} from '@/app/workspace/[workspaceId]/apps/components/types';

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-500',
  alpha:       'bg-amber-500/10 text-amber-600',
  ai:          'bg-blue-500/10 text-blue-500',
  core:        'bg-workspace-accent/10 text-workspace-accent',
};

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

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-xs text-foreground break-words">{value}</p>
    </div>
  );
}

/** Metadata for one app. Only rendered when the user explicitly asks for it. */
function AppDetailView({ mod, onBack }: { mod: OpenAppModule; onBack: () => void }) {
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 px-3 py-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors border-b border-border/50"
      >
        <ArrowLeft size={12} />
        <span>All apps</span>
      </button>

      {/* Avatar + name */}
      <div className="flex flex-col items-center gap-2 px-4 py-5 border-b border-border/50 text-center">
        <AppIcon
          record={{ avatarUrl: mod.logo_url, iconEmoji: mod.icon_emoji ?? null, name: mod.name }}
          size="lg"
        />
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
        {mod.module_name && <MetaRow label="Module" value={mod.module_name} />}
        {mod.maintainer && <MetaRow label="Maintainer" value={mod.maintainer} />}
        {mod.author && <MetaRow label="Author" value={mod.author} />}
        {mod.tier && <MetaRow label="Tier" value={mod.tier} />}
        {mod.version && <MetaRow label="Version" value={mod.version} />}
        {mod.license && <MetaRow label="License" value={mod.license} />}
        {mod.keywords && mod.keywords.length > 0 && (
          <MetaRow label="Keywords" value={mod.keywords.join(', ')} />
        )}
        {mod.module_path && (
          <div className="space-y-0.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Module path</p>
            <p className="break-all font-mono text-xs text-muted-foreground">{mod.module_path}</p>
          </div>
        )}

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

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const {
    currentWorkspaceId, openAppModule, setOpenAppModule, appDetailOpen, setAppDetailOpen,
  } = useWorkspaceStore();
  const tenant = useTenant();
  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');
  const pathname = usePathname();
  const isOnApps = pathname?.includes('/apps');

  const [apps, setApps] = useState<AppRecord[]>([]);
  const [panelLoading, setPanelLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{
    name: string;
    description: string;
    position: { top: number; left: number };
  } | null>(null);

  const showTooltip = (
    event: MouseEvent<HTMLElement>,
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
    if (!currentWorkspaceId) {
      setPanelLoading(false);
      return;
    }
    const apiBase = getApiUrl();
    const url = `${apiBase}/api/apps/?workspace_id=${encodeURIComponent(currentWorkspaceId)}`;
    authFetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: AppsResponse) => {
        setApps(data.apps.filter((a) => a.installed && a.url && a.enabled).map(toRecord));
      })
      .catch(() => { /* fail silently */ })
      .finally(() => setPanelLoading(false));
  }, [currentWorkspaceId]);

  // One flat, alphabetical list of every app the workspace can open. Splitting
  // by module (or any other property) is a grouping choice made in the page.
  const records = useMemo(
    () =>
      [...apps, ...tenant.apps.map(toTenantRecord)].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
      ),
    [apps, tenant.apps],
  );

  const activeAppUrl = openAppModule?.app_url ?? null;

  const openDetail = (record: AppRecord) => {
    setOpenAppModule(recordToOpenModule(record));
    setAppDetailOpen(true);
    hideTooltip();
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

  const appLinks = records.map((record) => {
    const isActive = activeAppUrl === record.url;
    return (
      <div
        key={record.id}
        className={cn(
          'group flex w-full items-center rounded-md transition-colors',
          isActive ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        )}
      >
        <Link
          href={`${basePath}?open=${encodeURIComponent(record.id)}`}
          onClick={() => setOpenAppModule(recordToOpenModule(record))}
          onMouseEnter={(e) => showTooltip(e, record.name, record.description || record.module)}
          onMouseLeave={hideTooltip}
          className={cn('flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-sm', isActive && 'font-medium')}
        >
          <AppIcon record={record} size="sm" />
          <span className="truncate">{record.name}</span>
        </Link>
        <button
          onClick={() => openDetail(record)}
          title="App details"
          className="mr-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-muted-foreground opacity-0 transition-opacity hover:text-foreground focus:opacity-100 group-hover:opacity-100"
        >
          <Info size={12} />
        </button>
      </div>
    );
  });

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

    // Metadata is opt-in: opening an app leaves this panel on the app list.
    if (appDetailOpen && openAppModule) {
      return <AppDetailView mod={openAppModule} onBack={() => setAppDetailOpen(false)} />;
    }

    return (
      <div className="space-y-0.5">
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
          <span>All apps</span>
        </Link>
        {appLinks}
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
      {appLinks}
      {tooltipPortal}
    </CollapsibleSection>
  );
}
