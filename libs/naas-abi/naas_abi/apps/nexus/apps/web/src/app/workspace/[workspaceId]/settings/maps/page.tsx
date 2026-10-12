'use client';

/**
 * Settings → Maps: the workspace's map layouts.
 *
 * Every layout (built-in, module graph layer, or one made here) can be hidden
 * for the whole workspace. Workspace layouts are SPARQL queries over the
 * workspace graphs returning ?label ?lat ?lng (and optionally ?uri ?detail
 * ?graph); each one is checked on save and can be run from here first.
 */
import { Suspense, useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, Loader2, Map as MapIcon, Plus, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { SettingsReloadButton } from '@/components/settings/settings-reload';
import {
  SettingsEmpty, SettingsFilterSelect, SettingsLoading, SettingsNotice, SettingsPageHeader,
  SettingsSection, SettingsTableToolbar, countLabel, settingsTable,
} from '@/components/settings/settings-ui';
import { cn } from '@/lib/utils';
import { useMapsStore } from '@/stores/maps';
import { MapsLayerBrandIcon } from '@/app/workspace/[workspaceId]/maps/components/maps-layer-brand-icon';
import { type LayoutEntry, type LayoutKind, type WorkspaceMapLayout } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import { LayoutApiError, layoutsApi } from '@/app/workspace/[workspaceId]/maps/lib/layouts-api';
import { MapsLayerEditorForm } from '@/app/workspace/[workspaceId]/maps/components/maps-layer-editor-form';
import { MAPS_CATEGORIES } from '@/app/workspace/[workspaceId]/maps/lib/datasets';
import { layerGroupLabel } from '@/app/workspace/[workspaceId]/maps/lib/maps-layer-groups';
import { getWorkspaceLayerGroupId, removeWorkspaceLayerMeta } from '@/app/workspace/[workspaceId]/maps/lib/maps-workspace-layer-meta';
import { mapsLayerPath, mapsSettingsPath } from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { mapsDeploymentRestrictsLayerCatalog } from '@/app/workspace/[workspaceId]/maps/lib/maps-deployment';
import { useMapLayouts } from '@/app/workspace/[workspaceId]/maps/lib/use-map-layouts';

const KIND_LABEL: Record<LayoutKind, string> = {
  builtin: 'Built-in',
  graph: 'Graph layer',
  workspace: 'Workspace layer',
  imported: 'Imported GeoJSON (this browser)',
};
const NEW = 'new';

export default function MapsSettingsPage() {
  return <Suspense fallback={null}><MapsSettings /></Suspense>;
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof LayoutApiError && error.errors.length) return error.errors.join('\n');
  return error instanceof Error ? error.message : fallback;
}

function MapsSettings() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const selectedId = useSearchParams()?.get('layout');
  const { all, hidden, canEdit, workspaceLayouts, loading, error, customLayerGroups } = useMapLayouts();
  const applyLayouts = useMapsStore((s) => s.applyLayouts);
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const [toggling, setToggling] = useState<string | null>(null);
  const [tableError, setTableError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [groupFilter, setGroupFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Fresh from the server whenever the page opens.
  useEffect(() => { if (workspaceId) void loadLayouts(workspaceId, true); }, [workspaceId, loadLayouts]);

  const select = (id: string | null) =>
    router.push(id ? mapsSettingsPath(workspaceId, { layout: id }) : mapsSettingsPath(workspaceId), { scroll: false });

  const toggleShown = async (entry: LayoutEntry) => {
    setToggling(entry.id); setTableError(null);
    try {
      const result = await layoutsApi.setHidden(workspaceId, entry.id, !hidden.includes(entry.id));
      applyLayouts(workspaceId, { hidden: result.hidden });
    } catch (e) {
      setTableError(errorText(e, 'Could not change the layout'));
    } finally { setToggling(null); }
  };

  const catalogRestricted = mapsDeploymentRestrictsLayerCatalog();

  if (selectedId) {
    if (catalogRestricted && selectedId === NEW) {
      select(null);
      return null;
    }
    const layout = selectedId === NEW ? null : workspaceLayouts.find((l) => l.id === selectedId) ?? null;
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-2">
          <Button variant="secondary" onClick={() => select(null)}>
            <ArrowLeft size={16} /> Active layers
          </Button>
          <SettingsReloadButton />
        </div>
        {loading && selectedId !== NEW && !layout ? (
          <SettingsLoading />
        ) : selectedId !== NEW && !layout ? (
          <SettingsEmpty title={<>There is no workspace layer “{selectedId}”.</>} />
        ) : (
          <LayoutEditor
            key={selectedId}
            workspaceId={workspaceId}
            layout={layout}
            takenIds={new Set(all.map((e) => e.id))}
            canEdit={canEdit}
            customLayerGroups={customLayerGroups}
            onSavedGeoJson={(layerId) => router.push(mapsLayerPath(workspaceId, layerId))}
            onSaved={(saved) => {
              const rest = workspaceLayouts.filter((l) => l.id !== saved.id);
              applyLayouts(workspaceId, { layouts: [...rest, saved] });
              if (selectedId === NEW) select(saved.id);
            }}
            onDeleted={(id) => {
              applyLayouts(workspaceId, {
                layouts: workspaceLayouts.filter((l) => l.id !== id),
                hidden: hidden.filter((h) => h !== id),
              });
              select(null);
            }}
          />
        )}
      </div>
    );
  }

  const query = searchQuery.trim().toLowerCase();
  const rows = all.filter((entry) => {
    const shown = !hidden.includes(entry.id);
    return (groupFilter === 'all' || groupFilter === entry.category)
      && (statusFilter === 'all' || (statusFilter === 'shown') === shown)
      && (!query || [entry.title, entry.id, entry.description].some((t) => t.toLowerCase().includes(query)));
  });
  const shownCount = all.filter((e) => !hidden.includes(e.id)).length;

  return (
    <div className="min-w-0 space-y-6">
      <SettingsPageHeader
        title="Maps"
        badge={`${shownCount} shown`}
        description={
          catalogRestricted
            ? 'Organization facility layers for this deployment. Hidden layers disappear for every member of the workspace.'
            : 'Layers offered in Maps for this workspace. Hidden layers disappear for every member. Create or edit workspace layers with the same editor as File → New layer in Maps.'
        }
        actions={
          catalogRestricted ? undefined : (
            <Button onClick={() => select(NEW)}>
              <Plus size={16} /> New layer
            </Button>
          )
        }
      />

      {error && <SettingsNotice tone="error"><span role="alert">{error}</span></SettingsNotice>}
      {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
      {!canEdit && !loading && <SettingsNotice>Only workspace owners and admins can change map layers.</SettingsNotice>}

      <SettingsTableToolbar
        search={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search layers..."
        filters={
          <>
            <SettingsFilterSelect label="Group" value={groupFilter} onChange={setGroupFilter} options={[
              { value: 'all', label: 'All groups' },
              ...MAPS_CATEGORIES.map(({ id, label }) => ({ value: id, label })),
            ]} />
            <SettingsFilterSelect label="Status" value={statusFilter} onChange={setStatusFilter} options={[
              { value: 'all', label: 'All statuses' },
              { value: 'shown', label: 'Shown' },
              { value: 'hidden', label: 'Hidden' },
            ]} />
          </>
        }
        meta={`${countLabel(rows.length, all.length, 'layout')} · ${shownCount} shown · ${workspaceLayouts.length} workspace layout${workspaceLayouts.length === 1 ? '' : 's'}`}
      />

      <div className="max-h-[65vh] overflow-y-auto overflow-x-hidden border border-border bg-card">
        <table className={cn(settingsTable.table, 'table-fixed')}>
          <thead>
            <tr className={settingsTable.headRow}>
              <th className={settingsTable.th}>Name</th>
              <th className={cn(settingsTable.th, 'w-28')}>Group</th>
              <th className={cn(settingsTable.th, 'w-40')}>Type</th>
              <th className={cn(settingsTable.th, 'w-24')}>Shown</th>
            </tr>
          </thead>
          <tbody>
            {loading && !all.length && (
              <tr><td colSpan={4} className={cn(settingsTable.td, 'text-muted-foreground')}><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
            )}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={4} className="p-8 text-center text-muted-foreground">No layers match the current search and filters</td></tr>
            )}
            {rows.map((entry) => {
              const shown = !hidden.includes(entry.id);
              const editable = entry.kind === 'workspace';
              return (
                <tr
                  key={entry.id}
                  onClick={editable ? () => select(entry.id) : undefined}
                  className={cn(settingsTable.row, editable && 'cursor-pointer')}
                >
                  <td className={cn(settingsTable.td, 'max-w-0')}>
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted">
                        <MapsLayerBrandIcon entry={entry} size={20} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className={cn('truncate font-medium', !shown && 'text-muted-foreground')} title={entry.title}>
                          {entry.title}
                        </div>
                        <div
                          className="truncate text-xs text-muted-foreground"
                          title={[entry.id, entry.description].filter(Boolean).join(' · ')}
                        >
                          <span className="font-mono">{entry.id}</span>{entry.description ? ` · ${entry.description}` : ''}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className={cn(settingsTable.td, 'max-w-0')}>
                    <Badge variant="outline" className="max-w-full truncate">
                      {layerGroupLabel(entry.category, customLayerGroups)}
                    </Badge>
                  </td>
                  <td className={cn(settingsTable.td, 'max-w-0 truncate text-muted-foreground')} title={KIND_LABEL[entry.kind]}>
                    {KIND_LABEL[entry.kind]}
                  </td>
                  <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                    <span className="inline-flex items-center gap-2">
                      <Checkbox
                        checked={shown}
                        disabled={!canEdit || toggling === entry.id}
                        onCheckedChange={() => void toggleShown(entry)}
                        aria-label={`${entry.title} shown`}
                      />
                      {toggling === entry.id && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LayoutEditor({
  workspaceId,
  layout,
  takenIds,
  canEdit,
  customLayerGroups,
  onSaved,
  onSavedGeoJson,
  onDeleted,
}: {
  workspaceId: string;
  layout: WorkspaceMapLayout | null;
  takenIds: Set<string>;
  canEdit: boolean;
  customLayerGroups: ReturnType<typeof useMapLayouts>['customLayerGroups'];
  onSaved: (layout: WorkspaceMapLayout) => void;
  onSavedGeoJson: (layerId: string) => void;
  onDeleted: (id: string) => void;
}) {
  const isNew = layout === null;
  const [busy, setBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const { confirm, dialog: confirmDialog } = useConfirm();

  const remove = async () => {
    if (!layout) return;
    const ok = await confirm({
      title: `Delete “${layout.title}”?`,
      description: 'The layer is removed from Maps for every member of this workspace.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!ok) return;
    setBusy(true);
    setDeleteError(null);
    try {
      await layoutsApi.remove(workspaceId, layout.id);
      removeWorkspaceLayerMeta(workspaceId, layout.id);
      onDeleted(layout.id);
    } catch (e) {
      setDeleteError(errorText(e, 'Could not delete the layer'));
      setBusy(false);
    }
  };

  const initialGroupId = layout
    ? getWorkspaceLayerGroupId(workspaceId, layout.id) ?? 'custom'
    : 'custom';

  return (
    <div className="space-y-6">
      {confirmDialog}
      <SettingsPageHeader
        title={isNew ? 'New layer' : layout.title}
        badge={isNew ? 'Draft' : 'Workspace layer'}
        description="Same editor as File → New layer in Maps: GeoJSON (browser-only) or SPARQL over workspace graphs (shared)."
        actions={
          <>
            {!isNew && (
              <Button variant="secondary" onClick={() => window.open(mapsLayerPath(workspaceId, layout.id), '_self')}>
                <MapIcon size={16} /> Open in Maps
              </Button>
            )}
            {!isNew && canEdit && (
              <Button variant="destructive-ghost" onClick={() => void remove()} disabled={busy}>
                <Trash2 size={16} /> Delete
              </Button>
            )}
          </>
        }
      />

      {!canEdit && <SettingsNotice>Only workspace owners and admins can save SPARQL workspace layers.</SettingsNotice>}
      {deleteError ? <SettingsNotice tone="error"><span role="alert">{deleteError}</span></SettingsNotice> : null}

      <SettingsSection title="Layer">
        <MapsLayerEditorForm
          key={layout?.id ?? 'new'}
          variant="page"
          workspaceId={workspaceId}
          takenIds={takenIds}
          customLayerGroups={customLayerGroups}
          canEdit={canEdit}
          workspaceLayout={layout}
          initialGroupId={initialGroupId}
          onSavedWorkspace={onSaved}
          onSavedGeoJson={onSavedGeoJson}
        />
      </SettingsSection>
    </div>
  );
}
