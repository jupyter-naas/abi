'use client';

import { useEffect, useState } from 'react';
import {
  LayoutGrid, Bot, Store, ArrowLeft, ExternalLink,
  Info, KeyRound, Copy, Check, Tag,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, OpenAppModule } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { APP_CATEGORIES } from '@/lib/app-constants';

interface ModuleInfo {
  module_path: string;
  name: string;
  description?: string;
  logo_url: string | null;
  category: string;
  installed: boolean;
  app_url?: string | null;
  demo_login?: string | null;
  demo_password?: string | null;
  maintainer?: string | null;
  tier?: string | null;
}

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-500',
  alpha:       'bg-amber-500/10 text-amber-600',
  ai:          'bg-blue-500/10 text-blue-500',
  core:        'bg-workspace-accent/10 text-workspace-accent',
};

function ModuleIcon({ mod, size = 14 }: { mod: Pick<ModuleInfo, 'logo_url' | 'name'>; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (mod.logo_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={mod.logo_url}
        alt={mod.name}
        style={{ width: size, height: size }}
        className="rounded object-cover flex-shrink-0"
        onError={() => setFailed(true)}
      />
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
        <ModuleIcon mod={mod} size={40} />
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

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId, setActivePanelSection, openAppModule } = useWorkspaceStore();
  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');
  const marketplacePath = getWorkspacePath(currentWorkspaceId, '/marketplace?type=applications');
  const pathname = usePathname();
  const isOnApps = pathname?.includes('/apps');

  const [apps, setApps] = useState<ModuleInfo[]>([]);
  const [panelLoading, setPanelLoading] = useState(true);

  useEffect(() => {
    const apiBase = getApiUrl();
    authFetch(`${apiBase}/api/modules/`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: { installed: ModuleInfo[]; available: ModuleInfo[] }) => {
        setApps(
          data.installed.filter(
            (m) => (APP_CATEGORIES.has(m.category) || m.app_url) && m.app_url,
          ),
        );
      })
      .catch(() => { /* fail silently */ })
      .finally(() => setPanelLoading(false));
  }, []);

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
          apps.map((mod) => (
            <Link
              key={mod.module_path}
              href={`${basePath}?open=${encodeURIComponent(mod.module_path)}`}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                openAppModule?.module_path === mod.module_path
                  ? 'bg-muted text-foreground font-medium'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <ModuleIcon mod={mod} size={14} />
              <span className="truncate">{mod.name}</span>
            </Link>
          ))
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
      {apps.map((mod) => {
        const isActive = openAppModule?.module_path === mod.module_path;
        return (
          <Link
            key={mod.module_path}
            href={`${basePath}?open=${encodeURIComponent(mod.module_path)}`}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
              isActive
                ? 'bg-muted text-foreground font-medium'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            <ModuleIcon mod={mod} size={14} />
            <span className="truncate">{mod.name}</span>
          </Link>
        );
      })}
    </CollapsibleSection>
  );
}
