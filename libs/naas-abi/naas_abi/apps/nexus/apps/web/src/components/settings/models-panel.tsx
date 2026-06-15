'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Check,
  CheckCircle,
  Cloud,
  Search,
  SlidersHorizontal,
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
  description?: string | null;
  tags?: string[];
  slug?: string | null;
  privacy_policy_url?: string | null;
  terms_of_service_url?: string | null;
  status_page_url?: string | null;
  headquarters?: string | null;
  datacenters?: string[] | null;
};

type SortKey = 'model' | 'provider' | 'context' | 'status';
type SortDirection = 'asc' | 'desc';
type StatusFilter = 'configured' | 'not_configured' | 'all';

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'configured', label: 'Configured' },
  { value: 'not_configured', label: 'Not configured' },
  { value: 'all', label: 'All' },
];

// Columns map 1:1 to the backend ModelCatalogEntry properties. `defaultVisible`
// seeds the initial table; the user can add/remove any of them via the Columns
// menu, and the selection is persisted to localStorage.
type ColumnKey =
  | 'image'
  | 'name'
  | 'model_id'
  | 'canonical_id'
  | 'provider'
  | 'provider_id'
  | 'module_path'
  | 'description'
  | 'context_window'
  | 'status';

type ColumnMeta = {
  key: ColumnKey;
  label: string;
  sortBy?: SortKey;
  defaultVisible: boolean;
};

const COLUMN_META: ColumnMeta[] = [
  { key: 'image', label: 'Image', defaultVisible: true },
  { key: 'name', label: 'Name', sortBy: 'model', defaultVisible: true },
  { key: 'model_id', label: 'Model ID', defaultVisible: true },
  { key: 'canonical_id', label: 'Canonical ID', defaultVisible: false },
  { key: 'provider', label: 'Provider', sortBy: 'provider', defaultVisible: true },
  { key: 'provider_id', label: 'Provider ID', defaultVisible: false },
  { key: 'module_path', label: 'Module path', defaultVisible: false },
  { key: 'description', label: 'Description', defaultVisible: true },
  { key: 'context_window', label: 'Context', sortBy: 'context', defaultVisible: true },
  { key: 'status', label: 'Status', sortBy: 'status', defaultVisible: true },
];

const DEFAULT_VISIBLE_COLUMNS = COLUMN_META.filter((c) => c.defaultVisible).map((c) => c.key);
// Bumped to v2 so the new default (Description column visible) applies to users
// who already had a persisted column selection.
const COLUMN_STORAGE_KEY = 'models-panel-visible-columns-v2';

const formatContext = (ctx: number | null) => {
  if (!ctx) return '—';
  return ctx >= 1000 ? `${(ctx / 1000).toFixed(0)}K` : `${ctx}`;
};

// Fixed widths keep the logo column from being stretched by long content in
// sibling columns (e.g. a multi-line description), guaranteeing a square logo.
const columnWidthClass = (key: ColumnKey): string => {
  switch (key) {
    case 'image':
      return 'w-[52px]';
    case 'description':
      return 'max-w-xs';
    default:
      return '';
  }
};

export function ModelsPanel() {
  const router = useRouter();
  const params = useParams();
  const workspaceId = (params?.workspaceId as string | undefined) ?? '';

  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [providerFilter, setProviderFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('configured');
  const [sortKey, setSortKey] = useState<SortKey>('model');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [visibleColumns, setVisibleColumns] = useState<Set<ColumnKey>>(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(COLUMN_STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as ColumnKey[];
          const known = parsed.filter((k) => COLUMN_META.some((c) => c.key === k));
          if (known.length) return new Set(known);
        }
      } catch {
        // ignore malformed storage and fall back to defaults
      }
    }
    return new Set(DEFAULT_VISIBLE_COLUMNS);
  });
  const [columnsMenuOpen, setColumnsMenuOpen] = useState(false);
  const columnsMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void fetchAll();
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        COLUMN_STORAGE_KEY,
        JSON.stringify(Array.from(visibleColumns))
      );
    } catch {
      // storage may be unavailable (private mode); column choices stay in-memory
    }
  }, [visibleColumns]);

  useEffect(() => {
    if (!columnsMenuOpen) return;
    const onMouseDown = (e: MouseEvent) => {
      if (columnsMenuRef.current && !columnsMenuRef.current.contains(e.target as Node)) {
        setColumnsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [columnsMenuOpen]);

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

  const providersById = useMemo(() => {
    const map = new Map<string, Provider>();
    providers.forEach((p) => map.set(p.id, p));
    return map;
  }, [providers]);

  const configuredCount = useMemo(
    () => models.filter((m) => m.configured).length,
    [models]
  );

  const orderedVisibleColumns = useMemo(
    () => COLUMN_META.filter((c) => visibleColumns.has(c.key)),
    [visibleColumns]
  );

  const toggleColumn = (key: ColumnKey) => {
    setVisibleColumns((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size === 1) return next; // always keep at least one column
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const openModel = (model: Model) => {
    const base = workspaceId
      ? `/workspace/${workspaceId}/settings/models`
      : '/settings/models';
    router.push(`${base}/${encodeURIComponent(model.canonical_id)}`);
  };

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

  const renderImage = (model: Model, provider: Provider | undefined) => {
    const raw = model.image ?? provider?.logo_url ?? null;
    const src = raw ? (raw.startsWith('http') ? raw : `${getApiBase()}${raw}`) : null;
    // Wrapped in a flex box so the fixed-size square stays vertically centered
    // and never stretches, regardless of how tall the row grows (e.g. when the
    // description column wraps to multiple lines).
    return (
      <div className="flex items-center">
        <div className="flex h-9 w-9 flex-none items-center justify-center overflow-hidden rounded-lg border bg-muted">
          {src ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={src}
              alt={model.name ?? model.provider_id}
              className="h-full w-full object-contain p-0.5"
            />
          ) : (
            <Cloud size={18} className="text-muted-foreground" />
          )}
        </div>
      </div>
    );
  };

  const renderCell = (key: ColumnKey, model: Model, provider: Provider | undefined) => {
    switch (key) {
      case 'image':
        return renderImage(model, provider);
      case 'name':
        return <span className="font-medium">{model.name ?? model.canonical_id}</span>;
      case 'model_id':
        return <code className="font-mono text-xs text-muted-foreground">{model.model_id}</code>;
      case 'canonical_id':
        return <code className="font-mono text-xs text-muted-foreground">{model.canonical_id}</code>;
      case 'provider':
        return <span>{provider?.name ?? model.provider}</span>;
      case 'provider_id':
        return <code className="font-mono text-xs text-muted-foreground">{model.provider_id}</code>;
      case 'module_path':
        return <code className="font-mono text-xs text-muted-foreground">{model.module_path}</code>;
      case 'description':
        return model.description ? (
          <p className="max-w-xs text-xs text-muted-foreground line-clamp-2">{model.description}</p>
        ) : (
          <span className="text-muted-foreground">—</span>
        );
      case 'context_window':
        return <span className="text-muted-foreground">{formatContext(model.context_window)}</span>;
      case 'status':
        return model.configured ? (
          <div className="inline-flex items-center gap-1.5 rounded-full bg-green-100 dark:bg-green-950 px-2 py-0.5 text-xs font-medium text-green-700 dark:text-green-300">
            <CheckCircle size={12} />
            Configured
          </div>
        ) : (
          <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 dark:bg-amber-950 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-300">
            <XCircle size={12} />
            Not configured
          </div>
        );
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading models...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
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

            <div className="relative" ref={columnsMenuRef}>
              <button
                onClick={() => setColumnsMenuOpen((open) => !open)}
                className={cn(
                  'inline-flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm transition-colors hover:bg-muted',
                  columnsMenuOpen && 'bg-muted'
                )}
              >
                <SlidersHorizontal size={16} />
                Columns
                <span className="rounded-full bg-muted px-1.5 text-xs text-muted-foreground">
                  {orderedVisibleColumns.length}
                </span>
              </button>
              {columnsMenuOpen && (
                <div className="absolute right-0 z-20 mt-2 w-56 rounded-lg border bg-background p-1 shadow-lg">
                  <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                    Toggle columns
                  </div>
                  {COLUMN_META.map((col) => {
                    const checked = visibleColumns.has(col.key);
                    const isLast = checked && visibleColumns.size === 1;
                    return (
                      <button
                        key={col.key}
                        onClick={() => toggleColumn(col.key)}
                        disabled={isLast}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted',
                          isLast && 'cursor-not-allowed opacity-50'
                        )}
                      >
                        <span
                          className={cn(
                            'flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border',
                            checked ? 'border-primary bg-primary text-primary-foreground' : 'border-input'
                          )}
                        >
                          {checked && <Check size={12} />}
                        </span>
                        {col.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-lg border overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm">
                  {orderedVisibleColumns.map((col) =>
                    col.sortBy ? (
                      <th key={col.key} className={cn('p-3 font-medium', columnWidthClass(col.key))}>
                        <button
                          onClick={() => handleSort(col.sortBy!)}
                          className="inline-flex items-center gap-1.5 hover:text-foreground"
                        >
                          {col.label}
                          {renderSortIcon(col.sortBy)}
                        </button>
                      </th>
                    ) : (
                      <th key={col.key} className={cn('p-3 font-medium', columnWidthClass(col.key))}>
                        {col.label}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {sortedModels.length === 0 ? (
                  <tr>
                    <td
                      colSpan={orderedVisibleColumns.length}
                      className="p-8 text-center text-muted-foreground"
                    >
                      No models match the current filters
                    </td>
                  </tr>
                ) : (
                  sortedModels.map((model) => {
                    const provider = providersById.get(model.provider_id);
                    return (
                      <tr
                        key={`${model.provider_id}-${model.canonical_id}`}
                        onClick={() => openModel(model)}
                        className="cursor-pointer border-b transition-colors last:border-0 hover:bg-muted/50"
                      >
                        {orderedVisibleColumns.map((col) => (
                          <td
                            key={col.key}
                            className={cn('p-3 align-top text-sm', columnWidthClass(col.key))}
                          >
                            {renderCell(col.key, model, provider)}
                          </td>
                        ))}
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
