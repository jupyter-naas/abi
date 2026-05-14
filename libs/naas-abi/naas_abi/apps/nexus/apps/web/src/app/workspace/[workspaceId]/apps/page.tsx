'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  Search, Bot, X, Cpu, Tag, CheckCircle2, AlertTriangle,
  FileText, Presentation, Table2, Trello, Calendar, ExternalLink,
  LayoutGrid, GitBranch, Network, Workflow,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useTenant } from '@/contexts/tenant-context';

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

type ArtifactType = 'all' | 'agents' | 'applications' | 'tools' | 'ontologies' | 'workflows' | 'pipelines';
type StatusFilter = 'all' | 'installed' | 'available' | 'coming-soon';

// ---------------------------------------------------------------------------
// Static metadata
// ---------------------------------------------------------------------------

const TYPE_LABELS: Record<ArtifactType, string> = {
  all: 'All',
  agents: 'Agents',
  applications: 'Applications',
  tools: 'Tools',
  ontologies: 'Ontologies',
  workflows: 'Workflows',
  pipelines: 'Pipelines',
};

const TYPE_ICONS: Record<ArtifactType, React.ReactNode> = {
  all: <LayoutGrid size={13} />,
  agents: <Bot size={13} />,
  applications: <ExternalLink size={13} />,
  tools: <FileText size={13} />,
  ontologies: <Network size={13} />,
  workflows: <Workflow size={13} />,
  pipelines: <GitBranch size={13} />,
};

const MODULE_CATEGORY_TO_TYPE: Record<string, ArtifactType> = {
  ai: 'agents',
  domain: 'agents',
  application: 'applications',
  core: 'agents',
};

const CATEGORY_LABELS: Record<string, string> = {
  core: 'Core',
  ai: 'AI',
  application: 'Application',
  domain: 'Domain',
};

const CATEGORY_COLORS: Record<string, string> = {
  core: 'bg-workspace-accent/10 text-workspace-accent',
  ai: 'bg-blue-500/10 text-blue-500',
  application: 'bg-purple-500/10 text-purple-500',
  domain: 'bg-amber-500/10 text-amber-600',
};

// ---------------------------------------------------------------------------
// Static artifacts (tools + coming-soon categories)
// ---------------------------------------------------------------------------

interface StaticArtifact {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  type: ArtifactType;
  status: 'available' | 'coming-soon';
  url?: string;
}

const STATIC_ARTIFACTS: StaticArtifact[] = [
  {
    id: 'docs',
    name: 'Docs',
    description: 'Rich text editor for documentation, notes, and runbooks with agent assistance.',
    icon: <FileText size={22} />,
    type: 'tools',
    status: 'coming-soon',
  },
  {
    id: 'slides',
    name: 'Slides',
    description: 'Build and narrate presentations driven by your knowledge graph.',
    icon: <Presentation size={22} />,
    type: 'tools',
    status: 'coming-soon',
  },
  {
    id: 'sheets',
    name: 'Sheets',
    description: 'Intelligent spreadsheets with formula support and live data connectors.',
    icon: <Table2 size={22} />,
    type: 'tools',
    status: 'coming-soon',
  },
  {
    id: 'board',
    name: 'Board',
    description: 'Kanban boards and whiteboards to manage tasks and visual workflows.',
    icon: <Trello size={22} />,
    type: 'tools',
    status: 'coming-soon',
  },
  {
    id: 'calendar',
    name: 'Calendar',
    description: 'Schedule and timeline management synced with your agents.',
    icon: <Calendar size={22} />,
    type: 'tools',
    status: 'coming-soon',
  },
  {
    id: 'ontologies-coming-soon',
    name: 'Community Ontologies',
    description: 'Browse and install shared ontology modules contributed by the ABI community.',
    icon: <Network size={22} />,
    type: 'ontologies',
    status: 'coming-soon',
  },
  {
    id: 'workflows-coming-soon',
    name: 'Workflow Templates',
    description: 'Reusable multi-step agent workflows for common business and data processes.',
    icon: <Workflow size={22} />,
    type: 'workflows',
    status: 'coming-soon',
  },
  {
    id: 'pipelines-coming-soon',
    name: 'Pipeline Blueprints',
    description: 'Pre-built data ingestion and transformation pipelines ready to configure.',
    icon: <GitBranch size={22} />,
    type: 'pipelines',
    status: 'coming-soon',
  },
];

// ---------------------------------------------------------------------------
// Module avatar (shared between card and ID panel)
// ---------------------------------------------------------------------------

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
            imgClassName,
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

// ---------------------------------------------------------------------------
// Module card (agent / application)
// ---------------------------------------------------------------------------

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
        <span className={cn('self-start rounded-full px-2 py-0.5 text-xs font-medium', CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground')}>
          {CATEGORY_LABELS[mod.category] ?? mod.category}
        </span>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {mod.description || mod.module_path}
        </p>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Static artifact card (tools, ontologies, workflows, pipelines)
// ---------------------------------------------------------------------------

function StaticCard({ artifact }: { artifact: StaticArtifact }) {
  const inner = (
    <div
      className={cn(
        'group relative flex flex-col gap-3 rounded-xl border bg-card p-5 transition-all h-full',
        artifact.status === 'available'
          ? 'cursor-pointer hover:border-workspace-accent hover:shadow-md'
          : 'opacity-60 cursor-default',
      )}
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-workspace-accent/10 text-workspace-accent">
        {artifact.icon}
      </div>
      <div className="flex-1">
        <h3 className="font-semibold leading-tight">{artifact.name}</h3>
        <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{artifact.description}</p>
      </div>
      {artifact.status === 'coming-soon' && (
        <span className="self-start rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          Coming soon
        </span>
      )}
      {artifact.status === 'available' && (
        <ExternalLink size={14} className="absolute right-4 top-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      )}
    </div>
  );

  if (artifact.status === 'available' && artifact.url) {
    return <a href={artifact.url} target="_blank" rel="noreferrer noopener" className="h-full">{inner}</a>;
  }
  return inner;
}

// ---------------------------------------------------------------------------
// External app card (from tenant config)
// ---------------------------------------------------------------------------

function ExternalAppCard({ app }: { app: { name: string; url: string; description?: string | null; icon_emoji?: string | null } }) {
  return (
    <a href={app.url} target="_blank" rel="noreferrer noopener">
      <div className="group relative flex flex-col gap-3 rounded-xl border bg-card p-5 transition-all cursor-pointer hover:border-workspace-accent hover:shadow-md">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-workspace-accent/10 text-2xl">
          {app.icon_emoji ?? <ExternalLink size={22} className="text-workspace-accent" />}
        </div>
        <div>
          <h3 className="font-semibold leading-tight">{app.name}</h3>
          {app.description && <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{app.description}</p>}
        </div>
        <ExternalLink size={14} className="absolute right-4 top-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
    </a>
  );
}

// ---------------------------------------------------------------------------
// Agent ID Card panel
// ---------------------------------------------------------------------------

function AgentIdCard({ mod, onClose }: { mod: ModuleInfo; onClose: () => void }) {
  const isPortrait = mod.category === 'domain';

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-background shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Agent ID Card</span>
          <button onClick={onClose} className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <ModuleAvatar
            mod={mod}
            className={cn('w-full', isPortrait ? 'h-64' : 'flex h-44 items-center justify-center p-10')}
          />

          <div className="space-y-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold">{mod.name}</h2>
                {mod.slug && <p className="mt-0.5 font-mono text-xs text-muted-foreground">{mod.slug}</p>}
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

            <div className="flex flex-wrap gap-2">
              <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', CATEGORY_COLORS[mod.category] ?? 'bg-muted text-muted-foreground')}>
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

            {mod.description && (
              <p className="text-sm leading-relaxed text-muted-foreground">{mod.description}</p>
            )}

            {mod.system_prompt_preview && (
              <div className="rounded-lg border bg-muted/40 p-3">
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">System prompt</p>
                <p className="text-xs leading-relaxed text-foreground/80">{mod.system_prompt_preview}</p>
              </div>
            )}

            <div className="rounded-lg border bg-muted/30 p-3 space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Module</p>
              <p className="break-all font-mono text-xs text-muted-foreground">{mod.module_path}</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const ALL_TYPES: ArtifactType[] = ['all', 'agents', 'applications', 'tools', 'ontologies', 'workflows', 'pipelines'];

export default function MarketplacePage() {
  const searchParams = useSearchParams();
  const tenant = useTenant();

  const [typeFilter, setTypeFilter] = useState<ArtifactType>(() => {
    const t = searchParams?.get('type') as ArtifactType | null;
    return t && ALL_TYPES.includes(t) ? t : 'all';
  });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [data, setData] = useState<ModulesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedMod, setSelectedMod] = useState<ModuleInfo | null>(null);

  useEffect(() => {
    const t = searchParams?.get('type') as ArtifactType | null;
    if (t && ALL_TYPES.includes(t)) setTypeFilter(t);
  }, [searchParams]);

  useEffect(() => {
    setLoading(true);
    authFetch(`${getApiUrl()}/api/modules/`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((d: ModulesResponse) => setData(d))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  // Merge all modules into one flat list (deduplicated by module_path)
  const allModules = useMemo<ModuleInfo[]>(() => {
    if (!data) return [];
    const map = new Map<string, ModuleInfo>();
    for (const m of data.available) map.set(m.module_path, m);
    for (const m of data.installed) map.set(m.module_path, { ...map.get(m.module_path) ?? m, installed: true });
    return Array.from(map.values());
  }, [data]);

  // Tenant external apps as static artifacts
  const tenantArtifacts = useMemo<StaticArtifact[]>(() =>
    tenant.apps.map((app) => ({
      id: `external-${app.url}`,
      name: app.name,
      description: app.description ?? '',
      icon: app.icon_emoji
        ? <span className="text-2xl">{app.icon_emoji}</span>
        : <ExternalLink size={22} />,
      type: 'tools' as ArtifactType,
      status: 'available' as const,
      url: app.url,
    })),
  [tenant.apps]);

  const allStatic = useMemo(() => [...tenantArtifacts, ...STATIC_ARTIFACTS], [tenantArtifacts]);

  // Count per type for badge display
  const typeCounts = useMemo(() => {
    const counts: Partial<Record<ArtifactType, number>> = {};
    for (const m of allModules) {
      const t = MODULE_CATEGORY_TO_TYPE[m.category] ?? 'agents';
      counts[t] = (counts[t] ?? 0) + 1;
    }
    for (const s of allStatic) {
      counts[s.type] = (counts[s.type] ?? 0) + 1;
    }
    counts.all = allModules.length + allStatic.length;
    return counts;
  }, [allModules, allStatic]);

  // Filtered module results
  const filteredModules = useMemo(() => {
    return allModules.filter((m) => {
      const artifactType = MODULE_CATEGORY_TO_TYPE[m.category] ?? 'agents';
      if (typeFilter !== 'all' && artifactType !== typeFilter) return false;
      if (statusFilter === 'installed' && !m.installed) return false;
      if (statusFilter === 'available' && m.installed) return false;
      if (statusFilter === 'coming-soon') return false;
      if (search) {
        const q = search.toLowerCase();
        if (!m.name.toLowerCase().includes(q) && !m.description.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [allModules, typeFilter, statusFilter, search]);

  // Filtered static results
  const filteredStatic = useMemo(() => {
    return allStatic.filter((s) => {
      if (typeFilter !== 'all' && s.type !== typeFilter) return false;
      if (statusFilter === 'installed') return false;
      if (statusFilter === 'available' && s.status !== 'available') return false;
      if (statusFilter === 'coming-soon' && s.status !== 'coming-soon') return false;
      if (search) {
        const q = search.toLowerCase();
        if (!s.name.toLowerCase().includes(q) && !s.description.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [allStatic, typeFilter, statusFilter, search]);

  // Group modules by their sub-category label when showing all types
  const groupedModules = useMemo(() => {
    if (typeFilter !== 'all') return { '': filteredModules };
    return filteredModules.reduce<Record<string, ModuleInfo[]>>((acc, m) => {
      const key = CATEGORY_LABELS[m.category] ?? m.category;
      (acc[key] ??= []).push(m);
      return acc;
    }, {});
  }, [filteredModules, typeFilter]);

  // Group static by type when showing all
  const groupedStatic = useMemo(() => {
    if (typeFilter !== 'all') return { '': filteredStatic };
    return filteredStatic.reduce<Record<string, StaticArtifact[]>>((acc, s) => {
      const key = TYPE_LABELS[s.type];
      (acc[key] ??= []).push(s);
      return acc;
    }, {});
  }, [filteredStatic, typeFilter]);

  const totalResults = filteredModules.length + filteredStatic.length;
  const hasResults = totalResults > 0;

  return (
    <div className="flex h-full flex-col">
      <Header title="Marketplace" subtitle="Agents, applications, tools, ontologies, workflows and pipelines" />

      <div className="flex-1 overflow-auto">
        <div className="p-6 space-y-5">

          {/* Search bar */}
          <div className="relative max-w-2xl">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search the marketplace…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-10 w-full rounded-xl border bg-background pl-10 pr-4 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>

          {/* Type filter pills */}
          <div className="flex flex-wrap gap-2">
            {ALL_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                  typeFilter === t
                    ? 'bg-workspace-accent text-white shadow-sm'
                    : 'bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {TYPE_ICONS[t]}
                {TYPE_LABELS[t]}
                {typeCounts[t] !== undefined && (
                  <span className={cn('rounded-full px-1.5 py-0.5 text-xs tabular-nums', typeFilter === t ? 'bg-white/20' : 'bg-background')}>
                    {typeCounts[t]}
                  </span>
                )}
              </button>
            ))}

            {/* Status filter — separated by a thin divider */}
            <div className="mx-1 w-px self-stretch bg-border" />
            {(['all', 'installed', 'available', 'coming-soon'] as StatusFilter[]).map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={cn(
                  'rounded-full px-3 py-1.5 text-xs font-medium transition-colors',
                  statusFilter === s
                    ? 'bg-foreground text-background'
                    : 'bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {s === 'all' ? 'All status' : s === 'coming-soon' ? 'Coming soon' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-20 text-muted-foreground">
              <LayoutGrid size={20} className="mr-2 animate-pulse" />
              Loading marketplace…
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="rounded-lg bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load: {error}
            </div>
          )}

          {/* Empty */}
          {!loading && !error && !hasResults && (
            <p className="py-12 text-center text-sm text-muted-foreground">Nothing matches your search.</p>
          )}

          {/* Results */}
          {!loading && !error && hasResults && (
            <div className="space-y-10">
              {/* Module groups */}
              {Object.entries(groupedModules)
                .filter(([, mods]) => mods.length > 0)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([label, mods]) => (
                  <section key={label || 'modules'}>
                    {label && (
                      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        {label}
                      </h2>
                    )}
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {mods.map((mod) => (
                        <ModuleCard key={mod.module_path} mod={mod} onClick={() => setSelectedMod(mod)} />
                      ))}
                    </div>
                  </section>
                ))}

              {/* Static artifact groups (tools, ontologies, workflows, pipelines) */}
              {Object.entries(groupedStatic)
                .filter(([, items]) => items.length > 0)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([label, items]) => (
                  <section key={label || 'static'}>
                    {label && (
                      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                        {label}
                      </h2>
                    )}
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {items.map((artifact) =>
                        artifact.id.startsWith('external-') ? (
                          <ExternalAppCard
                            key={artifact.id}
                            app={{ name: artifact.name, url: artifact.url ?? '#', description: artifact.description }}
                          />
                        ) : (
                          <StaticCard key={artifact.id} artifact={artifact} />
                        ),
                      )}
                    </div>
                  </section>
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
