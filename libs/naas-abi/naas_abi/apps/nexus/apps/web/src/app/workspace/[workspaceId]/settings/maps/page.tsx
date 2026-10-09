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
import { ArrowLeft, Loader2, Map as MapIcon, Play, Plus, Save, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Select, Textarea } from '@/components/ui/input';
import { SettingsReloadButton } from '@/components/settings/settings-reload';
import {
  SettingsEmpty, SettingsField, SettingsFilterSelect, SettingsLoading, SettingsNotice, SettingsPageHeader,
  SettingsSection, SettingsTableToolbar, countLabel, settingsTable,
} from '@/components/settings/settings-ui';
import { getApiUrl } from '@/lib/config';
import { cn } from '@/lib/utils';
import { authFetch } from '@/stores/auth';
import { useMapsStore } from '@/stores/maps';
import { mapsIconMap } from '@/app/workspace/[workspaceId]/maps/components/maps-section';
import { ALL_LAYOUTS_ID, type LayoutEntry, type LayoutKind, type WorkspaceMapLayout } from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import { LayoutApiError, blankLayout, layoutsApi, type LayoutDraft, type LayoutPreview } from '@/app/workspace/[workspaceId]/maps/lib/layouts-api';
import { mapsDatasetPath, mapsSettingsPath } from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { useMapLayouts } from '@/app/workspace/[workspaceId]/maps/lib/use-map-layouts';

const KIND_LABEL: Record<LayoutKind, string> = { builtin: 'Built-in', graph: 'Graph layer', workspace: 'Workspace layout' };
const GROUP_LABEL: Record<string, string> = { public: 'Public', private: 'Private', custom: 'Custom' };
const NEW = 'new';
const LAYOUT_ID = /^[a-z0-9][a-z0-9-]{0,47}$/;

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
  const { all, hidden, canEdit, workspaceLayouts, loading, error } = useMapLayouts();
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

  if (selectedId) {
    const layout = selectedId === NEW ? null : workspaceLayouts.find((l) => l.id === selectedId) ?? null;
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-2">
          <Button variant="secondary" onClick={() => select(null)}>
            <ArrowLeft size={16} /> All layouts
          </Button>
          <SettingsReloadButton />
        </div>
        {loading && selectedId !== NEW && !layout ? (
          <SettingsLoading />
        ) : selectedId !== NEW && !layout ? (
          <SettingsEmpty title={<>There is no workspace layout “{selectedId}”.</>} />
        ) : (
          <LayoutEditor
            key={selectedId}
            workspaceId={workspaceId}
            layout={layout}
            takenIds={new Set(all.map((e) => e.id))}
            canEdit={canEdit}
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
    <div className="space-y-6">
      <SettingsPageHeader
        title="Maps"
        badge={`${shownCount} shown`}
        description="The layouts the Maps section of this workspace offers. A hidden layout disappears from Maps for every member. Workspace layouts are SPARQL queries over the graphs this workspace can read."
        actions={canEdit && (
          <Button onClick={() => select(NEW)}>
            <Plus size={16} /> New layout
          </Button>
        )}
      />

      {error && <SettingsNotice tone="error"><span role="alert">{error}</span></SettingsNotice>}
      {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
      {!canEdit && !loading && <SettingsNotice>Only workspace owners and admins can change map layouts.</SettingsNotice>}

      <SettingsTableToolbar
        search={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search layouts..."
        filters={
          <>
            <SettingsFilterSelect label="Group" value={groupFilter} onChange={setGroupFilter} options={[
              { value: 'all', label: 'All groups' },
              { value: 'public', label: 'Public' },
              { value: 'private', label: 'Private' },
              { value: 'custom', label: 'Custom' },
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

      <div className={settingsTable.wrapper}>
        <table className={settingsTable.table}>
          <thead>
            <tr className={settingsTable.headRow}>
              <th className={settingsTable.th}>Name</th>
              <th className={settingsTable.th}>Group</th>
              <th className={settingsTable.th}>Type</th>
              <th className={cn(settingsTable.th, 'w-24')}>Shown</th>
            </tr>
          </thead>
          <tbody>
            {loading && !all.length && (
              <tr><td colSpan={4} className={cn(settingsTable.td, 'text-muted-foreground')}><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
            )}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={4} className="p-8 text-center text-muted-foreground">No layouts match the current search and filters</td></tr>
            )}
            {rows.map((entry) => {
              const Icon = mapsIconMap[entry.icon] || MapIcon;
              const shown = !hidden.includes(entry.id);
              const editable = entry.kind === 'workspace';
              return (
                <tr
                  key={entry.id}
                  onClick={editable ? () => select(entry.id) : undefined}
                  className={cn(settingsTable.row, editable && 'cursor-pointer')}
                >
                  <td className={settingsTable.td}>
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-muted"><Icon size={16} /></div>
                      <div className="min-w-0">
                        <div className={cn('font-medium', !shown && 'text-muted-foreground')}>{entry.title}</div>
                        <div className="truncate text-xs text-muted-foreground" title={entry.description}>
                          <span className="font-mono">{entry.id}</span>{entry.description ? ` · ${entry.description}` : ''}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className={settingsTable.td}><Badge variant="outline">{GROUP_LABEL[entry.category] ?? entry.category}</Badge></td>
                  <td className={cn(settingsTable.td, 'text-muted-foreground')}>{KIND_LABEL[entry.kind]}</td>
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

interface WorkspaceGraph { uri: string; label: string }

/** Graphs this workspace can read (the graph picker's list). */
function useWorkspaceGraphs(workspaceId: string): WorkspaceGraph[] | null {
  const [graphs, setGraphs] = useState<WorkspaceGraph[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    authFetch(`${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((packs: { graphs: { uri: string; label: string }[] }[]) => {
        if (cancelled) return;
        const seen = new Map<string, WorkspaceGraph>();
        for (const pack of packs) for (const g of pack.graphs) if (!seen.has(g.uri)) seen.set(g.uri, { uri: g.uri, label: g.label || g.uri });
        setGraphs([...seen.values()].sort((a, b) => a.label.localeCompare(b.label)));
      })
      .catch(() => { if (!cancelled) setGraphs([]); });
    return () => { cancelled = true; };
  }, [workspaceId]);
  return graphs;
}

function LayoutEditor({
  workspaceId, layout, takenIds, canEdit, onSaved, onDeleted,
}: {
  workspaceId: string;
  /** null: a new layout. */
  layout: WorkspaceMapLayout | null;
  takenIds: Set<string>;
  canEdit: boolean;
  onSaved: (layout: WorkspaceMapLayout) => void;
  onDeleted: (id: string) => void;
}) {
  const isNew = layout === null;
  const [id, setId] = useState(layout?.id ?? '');
  const [draft, setDraft] = useState<LayoutDraft>(() => {
    if (!layout) return blankLayout();
    const { id: _id, ...rest } = layout;
    return rest;
  });
  const [busy, setBusy] = useState<'save' | 'preview' | 'delete' | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [preview, setPreview] = useState<LayoutPreview | null>(null);
  const graphs = useWorkspaceGraphs(workspaceId);
  const { confirm, dialog: confirmDialog } = useConfirm();
  const readOnly = !canEdit;
  const set = <K extends keyof LayoutDraft>(key: K, value: LayoutDraft[K]) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setSaved(false);
  };

  const idError = isNew && id && (!LAYOUT_ID.test(id)
    ? 'Lowercase letters, digits and dashes, starting with a letter or digit (max 48).'
    : id === ALL_LAYOUTS_ID || takenIds.has(id) ? 'This id is already used by another layout.' : null);

  const save = async () => {
    setBusy('save'); setErrors([]); setSaved(false);
    try {
      onSaved(await layoutsApi.save(workspaceId, isNew ? id : layout.id, draft));
      setSaved(true);
    } catch (e) {
      setErrors(e instanceof LayoutApiError && e.errors.length ? e.errors : [errorText(e, 'Could not save the layout')]);
    } finally { setBusy(null); }
  };

  const run = async () => {
    setBusy('preview'); setErrors([]); setPreview(null);
    try {
      const result = await layoutsApi.preview(workspaceId, draft);
      if (result.errors.length) setErrors(result.errors); else setPreview(result);
    } catch (e) {
      setErrors([errorText(e, 'Could not run the query')]);
    } finally { setBusy(null); }
  };

  const remove = async () => {
    if (!layout) return;
    const ok = await confirm({
      title: `Delete “${layout.title}”?`,
      description: 'The layout is removed from Maps for every member of this workspace.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!ok) return;
    setBusy('delete');
    try {
      await layoutsApi.remove(workspaceId, layout.id);
      onDeleted(layout.id);
    } catch (e) {
      setErrors([errorText(e, 'Could not delete the layout')]);
      setBusy(null);
    }
  };

  const Icon = mapsIconMap[draft.icon] || MapIcon;
  const canSave = canEdit && busy === null && draft.title.trim() && draft.query.trim() && (!isNew || (id && !idError));

  return (
    <div className="space-y-6">
      {confirmDialog}
      <SettingsPageHeader
        title={isNew ? 'New layout' : layout.title}
        badge={isNew ? 'Draft' : 'Workspace layout'}
        description="Pins come from a SPARQL SELECT over the workspace graphs: ?label ?lat ?lng are required, ?uri (links a pin to its record), ?detail and ?graph are optional. Rows without valid coordinates are skipped; at most 2000 pins."
        actions={
          <>
            {!isNew && (
              <Button variant="secondary" onClick={() => window.open(mapsDatasetPath(workspaceId, layout.id), '_self')}>
                <MapIcon size={16} /> Open in Maps
              </Button>
            )}
            {!isNew && canEdit && (
              <Button variant="destructive-ghost" onClick={() => void remove()} disabled={busy !== null}>
                <Trash2 size={16} /> Delete
              </Button>
            )}
            {canEdit && (
              <Button onClick={() => void save()} disabled={!canSave}>
                {busy === 'save' ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save
              </Button>
            )}
          </>
        }
      />

      {!canEdit && <SettingsNotice>Only workspace owners and admins can change map layouts.</SettingsNotice>}
      {errors.length > 0 && (
        <SettingsNotice tone="error">
          <ul role="alert" className="list-disc space-y-0.5 pl-4">{errors.map((e) => <li key={e} className="whitespace-pre-line">{e}</li>)}</ul>
        </SettingsNotice>
      )}
      {saved && <SettingsNotice tone="success">Layout saved.</SettingsNotice>}

      <SettingsSection title="Layout">
        <div className="grid gap-4 md:grid-cols-2">
          <SettingsField label="Id" htmlFor="layout-id" hint={isNew ? (idError || 'Used in the Maps URL. It cannot be changed later.') : 'Cannot be changed.'}>
            <Input id="layout-id" value={id} disabled={!isNew || readOnly} placeholder="offices"
              onChange={(e) => setId(e.target.value.trim().toLowerCase())} className="font-mono" />
          </SettingsField>
          <SettingsField label="Title" htmlFor="layout-title">
            <Input id="layout-title" value={draft.title} disabled={readOnly} placeholder="Offices" onChange={(e) => set('title', e.target.value)} />
          </SettingsField>
          <SettingsField label="Description" htmlFor="layout-description" className="md:col-span-2">
            <Input id="layout-description" value={draft.description} disabled={readOnly} onChange={(e) => set('description', e.target.value)} />
          </SettingsField>
          <SettingsField label="Icon" htmlFor="layout-icon">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-muted"><Icon size={16} /></div>
              <Select id="layout-icon" value={draft.icon} disabled={readOnly} onChange={(e) => set('icon', e.target.value)}>
                {Object.keys(mapsIconMap).sort().map((name) => <option key={name} value={name}>{name}</option>)}
              </Select>
            </div>
          </SettingsField>
          <SettingsField label="Pin colour" htmlFor="layout-color">
            <div className="flex items-center gap-2">
              <input id="layout-color" type="color" value={draft.color} disabled={readOnly}
                onChange={(e) => set('color', e.target.value)} className="h-9 w-12 cursor-pointer border border-border bg-background p-1" />
              <span className="font-mono text-xs text-muted-foreground">{draft.color}</span>
            </div>
          </SettingsField>
        </div>
      </SettingsSection>

      <SettingsSection title="Graphs" description="Limit the query to some graphs; none selected reads every graph this workspace can read.">
        {graphs === null ? <SettingsLoading /> : graphs.length === 0 ? (
          <p className="text-sm text-muted-foreground">This workspace cannot read any graph yet.</p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {graphs.map((g) => (
              <Checkbox key={g.uri} label={g.label} title={g.uri} disabled={readOnly}
                checked={draft.graphs.includes(g.uri)}
                onCheckedChange={(on) => set('graphs', on ? [...draft.graphs, g.uri] : draft.graphs.filter((u) => u !== g.uri))} />
            ))}
          </div>
        )}
      </SettingsSection>

      <SettingsSection
        title="Query"
        actions={canEdit && (
          <Button variant="secondary" size="sm" onClick={() => void run()} disabled={busy !== null || !draft.query.trim()}>
            {busy === 'preview' ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run
          </Button>
        )}
      >
        <Textarea value={draft.query} disabled={readOnly} spellCheck={false} rows={14}
          onChange={(e) => set('query', e.target.value)} className="font-mono text-xs" aria-label="SPARQL query" />
        {preview && (
          <div className="mt-3 text-sm">
            <p className="font-medium">{preview.count} pin{preview.count === 1 ? '' : 's'}</p>
            {preview.pins.length > 0 && (
              <ul className="mt-1 max-h-48 overflow-auto text-xs text-muted-foreground">
                {preview.pins.slice(0, 20).map((pin) => (
                  <li key={pin.id} className="truncate">
                    <span className="text-foreground">{pin.label}</span> · {pin.lat.toFixed(4)}, {pin.lng.toFixed(4)}{pin.detail ? ` · ${pin.detail}` : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </SettingsSection>
    </div>
  );
}
