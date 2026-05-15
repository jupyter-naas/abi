'use client';

import { useEffect, useState } from 'react';
import { AppWindow, Bot, LayoutGrid, Store } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

interface ModuleInfo {
  module_path: string;
  name: string;
  logo_url: string | null;
  category: string;
  installed: boolean;
  app_url?: string | null;
}

const APP_CATEGORIES = new Set(['application', 'alpha']);

function ModuleIcon({ mod, size = 14 }: { mod: ModuleInfo; size?: number }) {
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

export function AppsSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const { currentWorkspaceId, setActivePanelSection } = useWorkspaceStore();
  const basePath = getWorkspacePath(currentWorkspaceId, '/apps');
  const marketplacePath = getWorkspacePath(currentWorkspaceId, '/marketplace?type=applications');
  const pathname = usePathname();
  const isOnApps = pathname?.includes('/apps');

  const [apps, setApps] = useState<ModuleInfo[]>([]);

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
      .catch(() => {/* fail silently — panel still shows fallback link */});
  }, []);

  return (
    <CollapsibleSection
      id="apps"
      icon={<AppWindow size={18} />}
      label="Apps"
      description="Web apps from your installed modules"
      href={basePath}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      {apps.length > 0 ? (
        apps.map((mod) => (
          <Link
            key={mod.module_path}
            href={basePath}
            className={cn(
              'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
              isOnApps
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
            isOnApps
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
    </CollapsibleSection>
  );
}
