'use client';

import { useMemo, useState } from 'react';
import { Loader2, Pencil, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { SettingsNotice, SettingsSection, countLabel, settingsTable } from '@/components/settings/settings-ui';
import { cn } from '@/lib/utils';
import { useMapsStore, workspaceLayoutsOf } from '@/stores/maps';
import { basemapsApi, type BasemapCategory, type WorkspaceBasemap } from '../lib/basemaps-api';
import { LayoutApiError } from '../lib/layouts-api';
import { basemapDefFromApi } from '../lib/maps-basemaps';
import { MapsBasemapThumb } from './maps-basemap-control';
import { MapsNewBasemapModal } from './maps-new-basemap-modal';
import { MapsAccessCell, type MapsPermissions } from './maps-settings-access';

const CATEGORY_LABEL: Record<BasemapCategory, string> = {
  standard: 'Standard',
  organization: 'Organization',
  custom: 'Custom',
};

const RENDERER_LABEL = { tile: 'Tiles', countries: 'Countries', geojson: 'GeoJSON' } as const;

function errorText(error: unknown, fallback: string): string {
  if (error instanceof LayoutApiError && error.errors.length) return error.errors.join('\n');
  return error instanceof Error ? error.message : fallback;
}

/**
 * Settings → Maps basemaps: the workspace catalog from `/api/maps/basemaps`.
 * Seeded basemaps can be edited and hidden; custom ones can also be deleted.
 */
export function MapsSettingsBasemapsSection({
  workspaceId,
  canEdit,
  permissions,
}: {
  workspaceId: string;
  canEdit: boolean;
  permissions?: MapsPermissions;
}) {
  const showAccess = canEdit && permissions !== undefined;
  const catalog = useMapsStore((s) => workspaceLayoutsOf(s, workspaceId));
  const applyLayouts = useMapsStore((s) => s.applyLayouts);
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const [editing, setEditing] = useState<WorkspaceBasemap | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = catalog.basemaps;
  const hidden = useMemo(() => new Set(catalog.hiddenBasemaps), [catalog.hiddenBasemaps]);
  const shownCount = rows.filter((row) => !hidden.has(row.id)).length;
  const takenIds = useMemo(() => new Set(rows.map((row) => row.id)), [rows]);

  const toggleShown = async (row: WorkspaceBasemap) => {
    setBusyId(row.id);
    setError(null);
    try {
      const result = await basemapsApi.setHidden(workspaceId, row.id, !hidden.has(row.id));
      applyLayouts(workspaceId, { hiddenBasemaps: result.hidden });
    } catch (e) {
      setError(errorText(e, 'Could not change the basemap'));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (row: WorkspaceBasemap) => {
    const ok = await confirm({
      title: `Delete “${row.title}”?`,
      description: 'The basemap is removed from the map type picker for every member of this workspace.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!ok) return;
    setBusyId(row.id);
    setError(null);
    try {
      await basemapsApi.remove(workspaceId, row.id);
      await loadLayouts(workspaceId, true);
    } catch (e) {
      setError(errorText(e, 'Could not delete the basemap'));
    } finally {
      setBusyId(null);
    }
  };

  const openEditor = (row: WorkspaceBasemap | null) => {
    setEditing(row);
    setModalOpen(true);
  };

  return (
    <>
      {confirmDialog}
      <SettingsSection
        title="Basemaps"
        description="Background map styles in the map type control, shared by every member of the workspace. Built-in and deployment basemaps can be renamed, restyled or hidden; custom ones can also be deleted."
        actions={
          canEdit ? (
            <Button variant="secondary" onClick={() => openEditor(null)}>
              <Plus size={16} /> New basemap
            </Button>
          ) : undefined
        }
      >
        {!canEdit ? (
          <SettingsNotice>Only workspace owners and admins can change basemaps.</SettingsNotice>
        ) : null}
        {error ? (
          <SettingsNotice tone="error">
            <span role="alert" className="whitespace-pre-line">{error}</span>
          </SettingsNotice>
        ) : null}

        <p className="mb-3 text-sm text-muted-foreground">
          {countLabel(shownCount, rows.length, 'basemap')} shown in the map type picker.
        </p>

        <div className="overflow-x-hidden border border-border bg-card">
          <table className={cn(settingsTable.table, 'table-fixed')}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Name</th>
                <th className={cn(settingsTable.th, 'w-32')}>Column</th>
                <th className={cn(settingsTable.th, 'w-28')}>Style</th>
                {showAccess ? <th className={cn(settingsTable.th, 'w-44')}>Access</th> : null}
                <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
                <th className={cn(settingsTable.th, 'w-24')} aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={showAccess ? 6 : 5} className={cn(settingsTable.td, 'text-muted-foreground')}>
                    <Loader2 size={14} className="mr-2 inline animate-spin" />
                    Loading…
                  </td>
                </tr>
              ) : null}
              {rows.map((row) => {
                const shown = !hidden.has(row.id);
                const busy = busyId === row.id;
                return (
                  <tr key={row.id} className={settingsTable.row}>
                    <td className={cn(settingsTable.td, 'max-w-0')}>
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="h-9 w-9 shrink-0 overflow-hidden border border-border bg-muted">
                          <MapsBasemapThumb workspaceId={workspaceId} def={basemapDefFromApi(row)} size={36} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div
                            className={cn('truncate font-medium', !shown && 'text-muted-foreground')}
                            title={row.title}
                          >
                            {row.title}
                          </div>
                          <div className="truncate font-mono text-xs text-muted-foreground" title={row.id}>
                            {row.id}
                            {row.system ? ' · seeded' : ''}
                            {row.shared_from ? ' · shared' : ''}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className={cn(settingsTable.td, 'truncate text-muted-foreground')}>
                      {CATEGORY_LABEL[row.category] ?? row.category}
                    </td>
                    <td className={cn(settingsTable.td, 'truncate text-muted-foreground')}>
                      {RENDERER_LABEL[row.renderer.kind] ?? row.renderer.kind}
                    </td>
                    {showAccess && permissions ? (
                      <td className={cn(settingsTable.td, 'max-w-0 text-xs')}>
                        <MapsAccessCell
                          workspaceId={workspaceId}
                          kind="basemap"
                          itemId={row.id}
                          permissions={permissions}
                        />
                      </td>
                    ) : null}
                    <td className={settingsTable.td}>
                      <span className="inline-flex items-center gap-2">
                        <Checkbox
                          checked={shown}
                          disabled={!canEdit || busy}
                          onCheckedChange={() => void toggleShown(row)}
                          aria-label={`${row.title} enabled in the map type picker`}
                        />
                        {busy ? <Loader2 size={12} className="animate-spin text-muted-foreground" /> : null}
                      </span>
                    </td>
                    <td className={settingsTable.td}>
                      {canEdit && !row.shared_from ? (
                        <span className="inline-flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEditor(row)}
                            aria-label={`Edit ${row.title}`}
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={busy || row.system}
                            onClick={() => void remove(row)}
                            aria-label={`Delete ${row.title}`}
                            title={
                              row.system
                                ? 'Provided by the deployment: hide it, or narrow its Access, instead of deleting it'
                                : 'Delete'
                            }
                          >
                            <Trash2 size={14} />
                          </Button>
                        </span>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SettingsSection>

      <MapsNewBasemapModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        workspaceId={workspaceId}
        takenIds={takenIds}
        basemap={editing}
      />
    </>
  );
}
