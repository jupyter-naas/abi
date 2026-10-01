'use client';

import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { AppWindow, Globe, Tag, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppsStore, type AppItem } from '@/stores/apps';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsPageHeader,
  SettingsSearch,
  settingsTable,
} from '@/components/settings/settings-ui';

const CATEGORY_BADGE: Record<string, 'primary' | 'warning' | 'neutral'> = {
  core: 'primary',
  alpha: 'warning',
};

function AppLogo({ app }: { app: AppItem }) {
  const [failed, setFailed] = useState(false);
  if (app.avatar_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={app.avatar_url}
        alt={app.name}
        className="h-9 w-9 object-cover"
        onError={() => setFailed(true)}
      />
    );
  }
  if (app.icon_emoji) {
    return (
      <div className="flex h-9 w-9 items-center justify-center bg-muted text-xl">
        {app.icon_emoji}
      </div>
    );
  }
  return (
    <div className="flex h-9 w-9 items-center justify-center bg-muted">
      <Globe size={18} className="text-muted-foreground" />
    </div>
  );
}

export default function AppsSettingsPage() {
  const params = useParams();
  const workspaceId = params?.workspaceId as string | undefined;
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const { apps, loading, fetchApps, toggleApp } = useAppsStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    void fetchApps(workspaceId);
  }, [workspaceId, fetchApps]);

  const installedApps = useMemo(
    () => apps.filter((a) => a.installed && a.url),
    [apps]
  );

  const filteredApps = useMemo(() => {
    const list = installedApps.slice().sort((a, b) => a.name.localeCompare(b.name));
    if (!searchQuery.trim()) return list;
    const q = searchQuery.toLowerCase();
    return list.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.description ?? '').toLowerCase().includes(q)
    );
  }, [installedApps, searchQuery]);

  if (!mounted) {
    return <SettingsLoading label="Loading apps…" />;
  }

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title={
          <span className="flex items-center gap-2">
            Apps
            <Badge>{filteredApps.length}</Badge>
          </span>
        }
        description="Enable or disable the marketplace apps available in this workspace"
      />

      {loading && installedApps.length === 0 ? (
        <SettingsLoading label="Loading apps…" />
      ) : installedApps.length === 0 ? (
        <SettingsEmpty
          icon={<AppWindow size={40} className="opacity-40" />}
          title="No apps installed"
          description="Install modules from the Marketplace to see their apps here."
        />
      ) : (
        <div className="space-y-4">
          <SettingsSearch value={searchQuery} onChange={setSearchQuery} placeholder="Search apps..." />

          <div className={settingsTable.wrapper}>
            <table className={settingsTable.table}>
              <thead>
                <tr className={settingsTable.headRow}>
                  <th className={settingsTable.th}>App</th>
                  <th className={settingsTable.th}>Category</th>
                  <th className={settingsTable.th}>Source</th>
                  <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
                </tr>
              </thead>
              <tbody>
                {filteredApps.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      {searchQuery ? `No apps match "${searchQuery}"` : 'No apps available'}
                    </td>
                  </tr>
                ) : (
                  filteredApps.map((app) => (
                    <tr key={app.app_id} className={settingsTable.row}>
                      <td className={cn(settingsTable.td, 'align-top')}>
                        <div className="flex min-h-[3.25rem] items-center gap-3">
                          <AppLogo app={app} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <p className="font-medium">{app.name}</p>
                              {app.url && (
                                <a
                                  href={app.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-muted-foreground hover:text-foreground"
                                  title="Open in new tab"
                                >
                                  <ExternalLink size={12} />
                                </a>
                              )}
                            </div>
                            <p
                              className="line-clamp-2 min-h-[2rem] text-xs text-muted-foreground"
                              title={app.description || undefined}
                            >
                              {app.description || ' '}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className={settingsTable.td}>
                        <Badge variant={CATEGORY_BADGE[app.category] ?? 'neutral'}>
                          <Tag size={9} />
                          {app.category}
                        </Badge>
                      </td>
                      <td className={cn(settingsTable.td, 'truncate text-muted-foreground')}>
                        {app.maintainer || app.module_name || app.module_path}
                      </td>
                      <td className={settingsTable.td}>
                        <Checkbox
                          checked={app.enabled}
                          onCheckedChange={() => toggleApp(app.app_id)}
                          aria-label={app.enabled ? 'Disable app' : 'Enable app'}
                          title={app.enabled ? 'Disable app' : 'Enable app'}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
