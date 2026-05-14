'use client';

import { useEffect, useState } from 'react';
import { Header } from '@/components/shell/header';
import { LayoutGrid, Package, Store, Search, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';

interface ModuleInfo {
  module_path: string;
  name: string;
  description: string;
  logo_url: string | null;
  category: string;
  installed: boolean;
}

interface ModulesResponse {
  installed: ModuleInfo[];
  available: ModuleInfo[];
}

const CATEGORY_LABELS: Record<string, string> = {
  core: 'Core',
  ai: 'AI',
  application: 'Application',
  domain: 'Domain',
};

const CATEGORY_COLORS: Record<string, string> = {
  core: 'bg-workspace-accent-10 text-workspace-accent',
  ai: 'bg-blue-500/10 text-blue-500',
  application: 'bg-purple-500/10 text-purple-500',
  domain: 'bg-amber-500/10 text-amber-600',
};

function ModuleCard({ mod }: { mod: ModuleInfo }) {
  return (
    <div className="glass-card flex flex-col gap-3 p-5 transition-all hover:border-primary/30">
      <div className="flex items-start gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-muted overflow-hidden">
          {mod.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={mod.logo_url}
              alt={mod.name}
              className="h-full w-full object-contain"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = 'none';
                e.currentTarget.parentElement?.classList.add('fallback-icon');
              }}
            />
          ) : (
            <Bot size={22} className="text-muted-foreground" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold leading-tight">{mod.name}</h3>
            {mod.installed && (
              <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
                Installed
              </span>
            )}
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-xs font-medium',
                CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground'
              )}
            >
              {CATEGORY_LABELS[mod.category] ?? mod.category}
            </span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
            {mod.description || mod.module_path}
          </p>
        </div>
      </div>
    </div>
  );
}

type Tab = 'installed' | 'marketplace';

export default function AppsPage() {
  const [tab, setTab] = useState<Tab>('installed');
  const [data, setData] = useState<ModulesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  useEffect(() => {
    setLoading(true);
    authFetch(`${getApiUrl()}/api/modules/`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((d: ModulesResponse) => setData(d))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const availableCategories = data
    ? Array.from(new Set(data.available.map((m) => m.category))).sort()
    : [];

  const filteredAvailable = (data?.available ?? []).filter((m) => {
    const matchesSearch =
      !search ||
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.description.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = categoryFilter === 'all' || m.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const groupedAvailable = filteredAvailable.reduce<Record<string, ModuleInfo[]>>(
    (acc, m) => {
      const key = CATEGORY_LABELS[m.category] ?? m.category;
      (acc[key] ??= []).push(m);
      return acc;
    },
    {}
  );

  return (
    <div className="flex h-full flex-col">
      <Header title="Apps" subtitle="Installed modules and marketplace" />

      <div className="flex-1 overflow-auto">
        {/* Tabs */}
        <div className="border-b px-6 pt-4">
          <div className="flex gap-1">
            {(['installed', 'marketplace'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  'flex items-center gap-2 rounded-t-md px-4 py-2 text-sm font-medium transition-colors',
                  tab === t
                    ? 'border-b-2 border-workspace-accent text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {t === 'installed' ? <Package size={15} /> : <Store size={15} />}
                {t === 'installed' ? 'Installed' : 'Marketplace'}
                {t === 'installed' && data && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-xs">
                    {data.installed.length}
                  </span>
                )}
                {t === 'marketplace' && data && (
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-xs">
                    {data.available.length}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6">
          {loading && (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <LayoutGrid size={20} className="mr-2 animate-pulse" />
              Loading modules…
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load modules: {error}
            </div>
          )}

          {/* Installed tab */}
          {!loading && !error && tab === 'installed' && (
            <div className="mx-auto max-w-5xl">
              {data?.installed.length === 0 ? (
                <p className="text-sm text-muted-foreground">No modules installed.</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {data?.installed.map((mod) => (
                    <ModuleCard key={mod.module_path} mod={mod} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Marketplace tab */}
          {!loading && !error && tab === 'marketplace' && (
            <div className="mx-auto max-w-5xl space-y-8">
              {/* Search + category filter */}
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative flex-1">
                  <Search
                    size={15}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                  />
                  <input
                    type="text"
                    placeholder="Search modules…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="h-9 w-full rounded-lg border bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {['all', ...availableCategories].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setCategoryFilter(cat)}
                      className={cn(
                        'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                        categoryFilter === cat
                          ? 'bg-workspace-accent text-white'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      )}
                    >
                      {cat === 'all' ? 'All' : (CATEGORY_LABELS[cat] ?? cat)}
                    </button>
                  ))}
                </div>
              </div>

              {Object.keys(groupedAvailable).length === 0 && (
                <p className="text-sm text-muted-foreground">No modules match your search.</p>
              )}

              {/* Grouped sections */}
              {Object.entries(groupedAvailable).sort().map(([category, mods]) => (
                <div key={category}>
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    {category}
                  </h2>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {mods.map((mod) => (
                      <ModuleCard key={mod.module_path} mod={mod} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
