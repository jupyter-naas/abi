'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { LayoutGrid, Package, Store, Search, Bot, X, Cpu, Tag, CheckCircle2, AlertTriangle } from 'lucide-react';
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
  model: string | null;
  slug: string | null;
  agent_type: string | null;
  system_prompt_preview: string | null;
  functional: boolean;
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

function ModuleAvatar({
  mod,
  className,
  imgClassName,
}: {
  mod: ModuleInfo;
  className?: string;
  imgClassName?: string;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const isPortrait = mod.category === 'domain';

  return (
    <div className={cn('relative overflow-hidden bg-muted', className)}>
      {mod.logo_url && !imgFailed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={mod.logo_url}
          alt={mod.name}
          className={cn(
            isPortrait ? 'h-full w-full object-cover object-top' : 'max-h-full max-w-full object-contain',
            imgClassName
          )}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <Bot size={36} className="text-muted-foreground/30" />
        </div>
      )}
      {isPortrait && mod.logo_url && !imgFailed && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-black/20 to-transparent" />
      )}
    </div>
  );
}

function ModuleCard({ mod, onClick }: { mod: ModuleInfo; onClick: () => void }) {
  const isPortrait = mod.category === 'domain';

  return (
    <button
      onClick={onClick}
      className="glass-card flex flex-col overflow-hidden text-left transition-all hover:border-primary/30 hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      <ModuleAvatar
        mod={mod}
        className={cn('w-full', isPortrait ? 'h-44' : 'flex h-32 items-center justify-center p-6')}
      />
      <div className="flex flex-col gap-1.5 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-1 font-semibold leading-tight">{mod.name}</h3>
          {mod.installed && (
            <span className="shrink-0 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
              Installed
            </span>
          )}
        </div>
        <span
          className={cn(
            'self-start rounded-full px-2 py-0.5 text-xs font-medium',
            CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground'
          )}
        >
          {CATEGORY_LABELS[mod.category] ?? mod.category}
        </span>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {mod.description || mod.module_path}
        </p>
      </div>
    </button>
  );
}

function AgentIdCard({ mod, onClose }: { mod: ModuleInfo; onClose: () => void }) {
  const isPortrait = mod.category === 'domain';

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-background shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-5 py-4">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Agent ID Card
          </span>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* Avatar hero */}
          <ModuleAvatar
            mod={mod}
            className={cn('w-full', isPortrait ? 'h-64' : 'flex h-44 items-center justify-center p-10')}
          />

          {/* Identity block */}
          <div className="space-y-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold">{mod.name}</h2>
                {mod.slug && (
                  <p className="mt-0.5 text-xs text-muted-foreground font-mono">{mod.slug}</p>
                )}
              </div>
              <div className="flex flex-col items-end gap-1.5">
                {mod.installed && (
                  <span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600">
                    <CheckCircle2 size={11} /> Installed
                  </span>
                )}
                {!mod.functional && (
                  <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-600">
                    <AlertTriangle size={11} /> Not functional yet
                  </span>
                )}
              </div>
            </div>

            {/* Badges row */}
            <div className="flex flex-wrap gap-2">
              <span
                className={cn(
                  'rounded-full px-2.5 py-0.5 text-xs font-medium',
                  CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground'
                )}
              >
                <Tag size={10} className="mr-1 inline" />
                {CATEGORY_LABELS[mod.category] ?? mod.category}
              </span>
              {mod.agent_type && (
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  {mod.agent_type}
                </span>
              )}
              {mod.model && (
                <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs font-medium text-blue-600">
                  <Cpu size={10} /> {mod.model}
                </span>
              )}
            </div>

            {/* Description */}
            {mod.description && (
              <div>
                <p className="text-sm text-muted-foreground leading-relaxed">{mod.description}</p>
              </div>
            )}

            {/* System prompt preview */}
            {mod.system_prompt_preview && (
              <div className="rounded-lg border bg-muted/40 p-3">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  System prompt
                </p>
                <p className="text-xs leading-relaxed text-foreground/80">
                  {mod.system_prompt_preview}
                </p>
              </div>
            )}

            {/* Technical info */}
            <div className="rounded-lg border bg-muted/30 p-3 space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Module
              </p>
              <p className="break-all font-mono text-xs text-muted-foreground">
                {mod.module_path}
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

type Tab = 'installed' | 'marketplace';

export default function AppsPage() {
  const searchParams = useSearchParams();
  const initialTab = (searchParams?.get('tab') === 'marketplace' ? 'marketplace' : 'installed') as Tab;
  const [tab, setTab] = useState<Tab>(initialTab);
  const [data, setData] = useState<ModulesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [selectedMod, setSelectedMod] = useState<ModuleInfo | null>(null);

  useEffect(() => {
    const t = searchParams?.get('tab') === 'marketplace' ? 'marketplace' : 'installed';
    setTab(t as Tab);
  }, [searchParams]);

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
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {data?.installed.map((mod) => (
                    <ModuleCard key={mod.module_path} mod={mod} onClick={() => setSelectedMod(mod)} />
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
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {mods.map((mod) => (
                      <ModuleCard key={mod.module_path} mod={mod} onClick={() => setSelectedMod(mod)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Agent ID Card side panel */}
      {selectedMod && (
        <AgentIdCard mod={selectedMod} onClose={() => setSelectedMod(null)} />
      )}
    </div>
  );
}
