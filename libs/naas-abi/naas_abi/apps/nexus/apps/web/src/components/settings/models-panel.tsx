'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckCircle,
  Cloud,
  SlidersHorizontal,
  XCircle,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Select } from '@/components/ui/input';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSearch,
  settingsTable,
} from '@/components/settings/settings-ui';

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
        <div className="flex h-9 w-9 flex-none items-center justify-center overflow-hidden border border-border bg-muted">
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
          <Badge variant="primary">
            <CheckCircle size={12} />
            Configured
          </Badge>
        ) : (
          <Badge variant="warning">
            <XCircle size={12} />
            Not configured
          </Badge>
        );
      default:
        return null;
    }
  };

  if (loading) {
    return <SettingsLoading label="Loading models…" />;
  }

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title={
          <span className="flex items-center gap-2">
            Models
            <Badge>{sortedModels.length}</Badge>
            <Badge variant="primary">{configuredCount} configured</Badge>
          </span>
        }
        description="All AI models discovered from naas_abi_marketplace.ai modules"
      />

      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          <p className="font-medium">Failed to load models</p>
          <p>{error}</p>
        </SettingsNotice>
      )}

      {models.length === 0 ? (
        <SettingsEmpty
          icon={<Cloud size={40} className="opacity-40" />}
          title="No models discovered"
          description="The naas_abi_marketplace.ai catalog is empty or unreachable."
        />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <SettingsSearch
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search by model, provider, or canonical id..."
              className="flex-1"
            />

            <Select value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)} className="sm:w-48">
              <option value="all">All providers</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>

            <div className="flex h-9 border border-border bg-background">
              {STATUS_FILTERS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setStatusFilter(opt.value)}
                  className={cn(
                    'px-3 text-sm transition-colors',
                    statusFilter === opt.value
                      ? 'bg-primary/10 font-medium text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="relative" ref={columnsMenuRef}>
              <Button
                variant="secondary"
                onClick={() => setColumnsMenuOpen((open) => !open)}
                className={cn(columnsMenuOpen && 'bg-muted')}
              >
                <SlidersHorizontal size={16} />
                Columns
                <Badge>{orderedVisibleColumns.length}</Badge>
              </Button>
              {columnsMenuOpen && (
                <div className="absolute right-0 z-20 mt-2 w-56 border border-border bg-popover p-1 shadow-lg">
                  <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                    Toggle columns
                  </div>
                  {COLUMN_META.map((col) => {
                    const checked = visibleColumns.has(col.key);
                    const isLast = checked && visibleColumns.size === 1;
                    return (
                      <Checkbox
                        key={col.key}
                        checked={checked}
                        onCheckedChange={() => toggleColumn(col.key)}
                        disabled={isLast}
                        label={col.label}
                        className="flex w-full px-2 py-1.5 hover:bg-muted"
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className={settingsTable.wrapper}>
            <table className={settingsTable.table}>
              <thead>
                <tr className={settingsTable.headRow}>
                  {orderedVisibleColumns.map((col) =>
                    col.sortBy ? (
                      <th key={col.key} className={cn(settingsTable.th, columnWidthClass(col.key))}>
                        <button
                          onClick={() => handleSort(col.sortBy!)}
                          className="inline-flex items-center gap-1.5 uppercase hover:text-foreground"
                        >
                          {col.label}
                          {renderSortIcon(col.sortBy)}
                        </button>
                      </th>
                    ) : (
                      <th key={col.key} className={cn(settingsTable.th, columnWidthClass(col.key))}>
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
                        className={cn(settingsTable.row, 'cursor-pointer')}
                      >
                        {orderedVisibleColumns.map((col) => (
                          <td
                            key={col.key}
                            className={cn(settingsTable.td, 'align-top', columnWidthClass(col.key))}
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

      <SettingsNotice icon={<AlertCircle size={14} />}>
        <div>
          <p className="font-medium text-foreground">Models come from the marketplace catalog</p>
          <p>
            Every provider module in <code>naas_abi_marketplace.ai.*</code> is listed here. Models tagged
            <strong> Not configured</strong> are visible but unusable until the owning module is enabled in
            <code> config.yaml</code> and its API key is present in <strong>Settings → Secrets</strong>.
          </p>
        </div>
      </SettingsNotice>
    </div>
  );
}
