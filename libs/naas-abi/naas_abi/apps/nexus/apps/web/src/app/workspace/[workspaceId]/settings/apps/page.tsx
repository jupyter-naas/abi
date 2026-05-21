'use client';

import { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { AppWindow, Globe, Search, X, Tag, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppsStore, type AppItem } from '@/stores/apps';

const CATEGORY_COLORS: Record<string, string> = {
  application: 'bg-purple-500/10 text-purple-500',
  alpha: 'bg-amber-500/10 text-amber-600',
  ai: 'bg-blue-500/10 text-blue-500',
  domain: 'bg-amber-500/10 text-amber-600',
  core: 'bg-workspace-accent/10 text-workspace-accent',
};

function AppLogo({ app }: { app: AppItem }) {
  const [failed, setFailed] = useState(false);
  if (app.avatar_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={app.avatar_url}
        alt={app.name}
        className="h-9 w-9 rounded-lg object-cover"
        onError={() => setFailed(true)}
      />
    );
  }
  if (app.icon_emoji) {
    return (
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-xl">
        {app.icon_emoji}
      </div>
    );
  }
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
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
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading apps...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Apps</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {filteredApps.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Enable or disable the marketplace apps available in this workspace
          </p>
        </div>
      </div>

      {loading && installedApps.length === 0 ? (
        <div className="flex items-center justify-center rounded-lg border border-dashed py-12 text-muted-foreground text-sm">
          <AppWindow size={18} className="mr-2 animate-pulse" /> Loading apps...
        </div>
      ) : installedApps.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <AppWindow size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No apps installed</h3>
          <p className="text-sm text-muted-foreground">
            Install modules from the Marketplace to see their apps here.
          </p>
        </div>
      ) : (
        <div>
          {/* Search */}
          <div className="mb-4 relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              placeholder="Search apps..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border bg-background pl-10 pr-10 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm">
                  <th className="p-3 font-medium">App</th>
                  <th className="p-3 font-medium">Category</th>
                  <th className="p-3 font-medium">Source</th>
                  <th className="p-3 font-medium w-24">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {filteredApps.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      {searchQuery
                        ? `No apps match "${searchQuery}"`
                        : 'No apps available'}
                    </td>
                  </tr>
                ) : (
                  filteredApps.map((app) => (
                    <tr
                      key={app.app_id}
                      className="border-b transition-colors hover:bg-muted/30"
                    >
                      <td className="p-3 align-top">
                        <div className="flex items-center gap-3 min-h-[3.25rem]">
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
                              className="text-xs text-muted-foreground line-clamp-2 min-h-[2rem]"
                              title={app.description || undefined}
                            >
                              {app.description || ' '}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="p-3">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium',
                            CATEGORY_COLORS[app.category] ??
                              'bg-muted text-muted-foreground'
                          )}
                        >
                          <Tag size={9} />
                          {app.category}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className="text-sm text-muted-foreground truncate">
                          {app.maintainer || app.module_name || app.module_path}
                        </span>
                      </td>
                      <td className="p-3">
                        <button
                          onClick={() => toggleApp(app.app_id)}
                          className={cn(
                            'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                            app.enabled ? 'bg-primary' : 'bg-muted'
                          )}
                          title={app.enabled ? 'Disable app' : 'Enable app'}
                        >
                          <span
                            className={cn(
                              'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
                              app.enabled ? 'translate-x-5' : 'translate-x-0.5'
                            )}
                          />
                        </button>
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
