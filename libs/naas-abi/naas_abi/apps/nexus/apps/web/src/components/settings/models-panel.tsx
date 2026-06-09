'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCircle,
  Cloud,
  RefreshCw,
  Search,
  X,
  XCircle,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { cn } from '@/lib/utils';

const getApiBase = () => getApiUrl();

type Model = {
  canonical_id: string;
  model_id: string;
  provider: string;
  provider_id: string;
  module_path: string;
  configured: boolean;
  name: string | null;
  description: string | null;
  image: string | null;
  context_window: number | null;
};

type Provider = {
  id: string;
  name: string;
  module_path: string;
  configured: boolean;
  logo_url: string | null;
  config_keys: string[];
  models: Model[];
};

type SortKey = 'model' | 'provider' | 'context' | 'status';
type SortDirection = 'asc' | 'desc';
type StatusFilter = 'configured' | 'not_configured' | 'all';

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'configured', label: 'Configured' },
  { value: 'not_configured', label: 'Not configured' },
  { value: 'all', label: 'All' },
];

export function ModelsPanel() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [providerFilter, setProviderFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('configured');
  const [sortKey, setSortKey] = useState<SortKey>('model');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchAll();
  }, []);

  const fetchAll = async () => {
    setError(null);
    try {
      const [providersRes, modelsRes] = await Promise.all([
        authFetch(`${getApiBase()}/api/providers/available`),
        authFetch(`${getApiBase()}/api/providers/models`),
      ]);
      if (!providersRes.ok) throw new Error(`Providers: HTTP ${providersRes.status}`);
      if (!modelsRes.ok) throw new Error(`Models: HTTP ${modelsRes.status}`);
      setProviders(await providersRes.json());
      setModels(await modelsRes.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load models');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    await fetchAll();
    setSyncing(false);
  };

  const providersById = useMemo(() => {
    const map = new Map<string, Provider>();
    providers.forEach((p) => map.set(p.id, p));
    return map;
  }, [providers]);

  const configuredCount = useMemo(
    () => models.filter((m) => m.configured).length,
    [models]
  );

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDirection('asc');
    }
  };

  const filteredModels = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return models.filter((m) => {
      if (statusFilter === 'configured' && !m.configured) return false;
      if (statusFilter === 'not_configured' && m.configured) return false;
      if (providerFilter !== 'all' && m.provider_id !== providerFilter) return false;
      if (q) {
        const haystack = [
          m.canonical_id,
          m.model_id,
          m.provider_id,
          m.provider,
          m.name ?? '',
        ].join(' ').toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [models, searchQuery, providerFilter, statusFilter]);

  const sortedModels = useMemo(() => {
    const sorted = [...filteredModels];
    const dir = sortDirection === 'asc' ? 1 : -1;
    sorted.sort((a, b) => {
      switch (sortKey) {
        case 'model': {
          const aKey = (a.name ?? a.canonical_id).toLowerCase();
          const bKey = (b.name ?? b.canonical_id).toLowerCase();
          return aKey.localeCompare(bKey) * dir;
        }
        case 'provider': {
          const aName = (providersById.get(a.provider_id)?.name ?? a.provider_id).toLowerCase();
          const bName = (providersById.get(b.provider_id)?.name ?? b.provider_id).toLowerCase();
          return aName.localeCompare(bName) * dir;
        }
        case 'context': {
          const aCtx = a.context_window ?? -1;
          const bCtx = b.context_window ?? -1;
          return (aCtx - bCtx) * dir;
        }
        case 'status': {
          // Configured first when ascending.
          const aVal = a.configured ? 0 : 1;
          const bVal = b.configured ? 0 : 1;
          return (aVal - bVal) * dir;
        }
        default:
          return 0;
      }
    });
    return sorted;
  }, [filteredModels, sortKey, sortDirection, providersById]);

  const renderSortIcon = (key: SortKey) => {
    if (sortKey !== key) {
      return <ArrowUpDown size={12} className="text-muted-foreground/50" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp size={12} className="text-foreground" />
    ) : (
      <ArrowDown size={12} className="text-foreground" />
    );
  };

  const SortHeader = ({ label, sortBy }: { label: string; sortBy: SortKey }) => (
    <th className="p-3 font-medium">
      <button
        onClick={() => handleSort(sortBy)}
        className="inline-flex items-center gap-1.5 hover:text-foreground"
      >
        {label}
        {renderSortIcon(sortBy)}
      </button>
    </th>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading models...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Models</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {sortedModels.length}
            </span>
            <span className="rounded-full bg-green-100 dark:bg-green-950 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-300">
              {configuredCount} configured
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            All AI models discovered from naas_abi_marketplace.ai modules
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50"
        >
          <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
          Sync Models
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
          <AlertCircle size={20} className="mt-0.5 flex-shrink-0 text-red-600 dark:text-red-500" />
          <div className="text-sm">
            <p className="font-medium text-red-800 dark:text-red-200">Failed to load models</p>
            <p className="text-red-700 dark:text-red-300">{error}</p>
          </div>
        </div>
      )}

      {models.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <Cloud size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No models discovered</h3>
          <p className="text-sm text-muted-foreground">
            The naas_abi_marketplace.ai catalog is empty or unreachable.
          </p>
        </div>
      ) : (
        <div>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by model, provider, or canonical id..."
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

            <select
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="all">All providers</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>

            <div className="flex rounded-lg border bg-background p-0.5">
              {STATUS_FILTERS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setStatusFilter(opt.value)}
                  className={cn(
                    'px-3 py-1.5 text-sm rounded-md transition-colors',
                    statusFilter === opt.value
                      ? 'bg-muted font-medium text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm">
                  <SortHeader label="Model" sortBy="model" />
                  <SortHeader label="Provider" sortBy="provider" />
                  <SortHeader label="Context" sortBy="context" />
                  <SortHeader label="Status" sortBy="status" />
                </tr>
              </thead>
              <tbody>
                {sortedModels.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      No models match the current filters
                    </td>
                  </tr>
                ) : (
                  sortedModels.map((model) => {
                    const provider = providersById.get(model.provider_id);
                    const logoUrl = provider?.logo_url ?? null;
                    return (
                      <tr key={`${model.provider_id}-${model.canonical_id}`} className="border-b last:border-0">
                        <td className="p-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg bg-muted">
                              {logoUrl ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                  src={logoUrl.startsWith('http') ? logoUrl : `${getApiBase()}${logoUrl}`}
                                  alt={model.provider_id}
                                  className="h-full w-full object-cover"
                                />
                              ) : (
                                <Cloud size={18} />
                              )}
                            </div>
                            <div>
                              <p className="font-medium">{model.name ?? model.canonical_id}</p>
                              <code className="text-xs text-muted-foreground font-mono">{model.model_id}</code>
                              {model.description && (
                                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{model.description}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="p-3 text-sm">
                          <div>{provider?.name ?? model.provider_id}</div>
                          <code className="text-xs text-muted-foreground font-mono">{model.module_path}</code>
                        </td>
                        <td className="p-3 text-sm text-muted-foreground">
                          {model.context_window
                            ? model.context_window >= 1000
                              ? `${(model.context_window / 1000).toFixed(0)}K`
                              : `${model.context_window}`
                            : '—'}
                        </td>
                        <td className="p-3">
                          {model.configured ? (
                            <div className="inline-flex items-center gap-1.5 rounded-full bg-green-100 dark:bg-green-950 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-300">
                              <CheckCircle size={12} />
                              Configured
                            </div>
                          ) : (
                            <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-950 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-300">
                              <XCircle size={12} />
                              Not configured
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
        <AlertCircle size={20} className="mt-0.5 flex-shrink-0 text-blue-600 dark:text-blue-500" />
        <div className="text-sm">
          <p className="font-medium text-blue-800 dark:text-blue-200">Models come from the marketplace catalog</p>
          <p className="text-blue-700 dark:text-blue-300">
            Every provider module in <code>naas_abi_marketplace.ai.*</code> is listed here. Models tagged
            <strong> Not configured</strong> are visible but unusable until the owning module is enabled in
            <code> config.yaml</code> and its API key is present in <strong>Settings → Secrets</strong>.
          </p>
        </div>
      </div>
    </div>
  );
}
