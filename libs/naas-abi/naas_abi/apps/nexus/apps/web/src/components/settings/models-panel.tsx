'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AlertCircle, CheckCircle, Cloud, SlidersHorizontal, XCircle } from 'lucide-react';
import { readAvailableProviders, readProviderModels } from '@/stores/models';
import { getApiUrl } from '@/lib/config';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { SettingsPageHeader, SettingsTableToolbar, countLabel } from '@/components/settings/settings-ui';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import { Notice } from '@/components/ui/notice';
import {
  SettingsTableClear,
  SettingsTableHead,
  SettingsTableNoMatch,
  useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import {
  CONFIGURED,
  MODEL_COLUMNS,
  MODEL_EXPORT_HEADERS,
  formatContext,
  modelCellValues,
  modelExportRow,
  modelRows,
  modelSearchTexts,
  modelSortValue,
  visibleColumnsFrom,
  type Model,
  type ModelColumnId,
  type ModelRow,
  type Provider,
} from './models-panel-model';
import { usePolicyHref } from '@/components/settings/use-policy-href';

const getApiBase = () => getApiUrl();

// Bumped to v2 so the new default (Description column visible) applies to users
// who already had a persisted column selection.
const COLUMN_STORAGE_KEY = 'models-panel-visible-columns-v2';

/**
 * Settings › Models, laid out as Settings › Users: a search, columns that sort and filter (the
 * provider and the status from their columns, Configured at first), pages, an export. The
 * Columns menu picks the columns shown; a row opens its model.
 */
export function ModelsPanel() {
  // Links keep the policy picked in the Settings column (`?policy=`).
  const policyHref = usePolicyHref();
  const router = useRouter();
  const params = useParams();
  const workspaceId = (params?.workspaceId as string | undefined) ?? '';

  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [visibleColumns, setVisibleColumns] = useState<Set<ModelColumnId>>(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(COLUMN_STORAGE_KEY);
        if (raw) return new Set(visibleColumnsFrom(JSON.parse(raw)));
      } catch {
        // ignore malformed storage and fall back to defaults
      }
    }
    return new Set(visibleColumnsFrom(null));
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
      // The catalogs the chat and the store read too: one request each.
      const [providersRes, modelsRes] = await Promise.all([readAvailableProviders(), readProviderModels()]);
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

  const rows = useMemo(() => modelRows(models, providers), [models, providers]);
  const configuredCount = useMemo(() => models.filter((m) => m.configured).length, [models]);

  // Every column filters, shown or not; the header draws the columns shown.
  const table = useSettingsTable({
    rows,
    columns: MODEL_COLUMNS,
    cellValues: modelCellValues,
    searchTexts: modelSearchTexts,
    sortValue: modelSortValue,
    initialSort: 'name',
    // The configured models at first, as the Status filter did.
    initialFilters: { status: { selected: [CONFIGURED] } },
  });
  const shown = table.shown;
  const orderedVisibleColumns = useMemo(
    () => MODEL_COLUMNS.filter((c) => visibleColumns.has(c.id)),
    [visibleColumns]
  );

  const toggleColumn = (key: ModelColumnId) => {
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
    router.push(policyHref(`${base}/${encodeURIComponent(model.canonical_id)}`));
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(MODEL_EXPORT_HEADERS, shown.map(modelExportRow), format, `models_${date}`, 'Models');
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

  const renderCell = (key: ModelColumnId, model: ModelRow, provider: Provider | undefined) => {
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
        return <span>{model.provider_name}</span>;
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
    return <Loading label="Loading models…" />;
  }

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Models"
        badge={`${configuredCount} configured`}
        description="The models of the marketplace AI modules"
        actions={<UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />}
      />

      {error && (
        <Notice tone="error" icon={<AlertCircle size={14} />}>
          <p className="font-medium">Failed to load models</p>
          <p>{error}</p>
        </Notice>
      )}

      {models.length === 0 ? (
        <EmptyState framed
          icon={<Cloud size={40} className="opacity-40" />}
          title="No models discovered"
          description="The naas_abi_marketplace.ai catalog is empty or unreachable."
        />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search by model, provider, or canonical id..."
            filters={
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
                    {MODEL_COLUMNS.map((col) => {
                      const checked = visibleColumns.has(col.id);
                      const isLast = checked && visibleColumns.size === 1;
                      return (
                        <Checkbox
                          key={col.id}
                          checked={checked}
                          onCheckedChange={() => toggleColumn(col.id)}
                          disabled={isLast}
                          label={col.label}
                          className="flex w-full px-2 py-1.5 hover:bg-muted"
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            }
            meta={
              <>
                {`${countLabel(shown.length, models.length, 'model')} · ${configuredCount} configured · ${providers.length} providers`}
                <SettingsTableClear table={table} />
              </>
            }
          />

          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={{ ...table, columns: orderedVisibleColumns }} />
              <tbody>
                {shown.length === 0 && (
                  <SettingsTableNoMatch colSpan={orderedVisibleColumns.length} noun="models" />
                )}
                {table.paged.pageRows.map((model) => {
                  const provider = providersById.get(model.provider_id);
                  return (
                    <tr
                      key={`${model.provider_id}-${model.canonical_id}`}
                      data-model={model.canonical_id}
                      onClick={() => openModel(model)}
                      className="cursor-pointer"
                    >
                      {orderedVisibleColumns.map((col) => (
                        <td key={col.id} className={cn('align-top', col.className)}>
                          {renderCell(col.id, model, provider)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <TablePager total={shown.length} paged={table.paged} />
        </div>
      )}

      <Notice icon={<AlertCircle size={14} />}>
        <div>
          <p className="font-medium text-foreground">Models come from the marketplace catalog</p>
          <p>
            Every provider module in <code>naas_abi_marketplace.ai.*</code> is listed here. Models tagged
            <strong> Not configured</strong> are visible but unusable until the owning module is enabled in
            <code> config.yaml</code> and its API key is present in <strong>Settings → Secrets</strong>.
          </p>
        </div>
      </Notice>
    </div>
  );
}
