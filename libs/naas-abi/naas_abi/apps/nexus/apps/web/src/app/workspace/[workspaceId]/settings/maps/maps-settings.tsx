'use client';

/**
 * Settings → Maps: feeds, the layers drawn from them, and basemaps.
 *
 * A feed is a data source: SPARQL over the workspace graphs, or a Nexus API
 * path (e.g. organization facilities, often seeded by the deployment). A layer
 * is what Maps lists and draws: a view on one feed — every feature, or only some
 * feature types — with its own title, color and icon. A feed keeps one layer at
 * least. The overview lists feeds ("Layers"); a feed's page edits its layers,
 * their colors and which are shown. Access is set per feed; hiding per layer,
 * or per feed from the Feed Layers table (built-in and graph layers are
 * one-layer feeds there).
 */
import { WORKSPACE_PAGE_DESCRIPTIONS } from '@/components/settings/settings-page-descriptions';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Map as MapIcon, Pencil, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { InstanceHeader } from '@/components/access/instance-header';
import { InstanceBack } from '@/components/settings/instance-form';
import {
  SettingsEmpty, SettingsLoading, SettingsNotice, SettingsPageHeader, SettingsSection,
  SettingsTableToolbar,
} from '@/components/settings/settings-ui';
import {
  SettingsTableClear, SettingsTableHead, SettingsTableNoMatch, useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import { cn } from '@/lib/utils';
import { useMapsStore } from '@/stores/maps';
import {
  hasFeatureTypes, isFeedLayout, isStoredFeed, type WorkspaceFeedLayer, type WorkspaceMapLayout,
} from '@/app/workspace/[workspaceId]/maps/lib/layouts';
import {
  LayoutApiError, feedLayerDraft, feedLayersApi, layoutsApi,
} from '@/app/workspace/[workspaceId]/maps/lib/layouts-api';
import { mapsIconMap } from '@/app/workspace/[workspaceId]/maps/lib/maps-icons';
import { facilityClassIcon } from '@/app/workspace/[workspaceId]/maps/lib/maps-facility-class-symbology';
import { MapsAccessCell, useMapsPermissions } from '@/app/workspace/[workspaceId]/maps/components/maps-settings-access';
import { MapsLayerEditorForm } from '@/app/workspace/[workspaceId]/maps/components/maps-layer-editor-form';
import {
  MapsFeedLayerForm, slugifyLayerId, useFeedTypes,
} from '@/app/workspace/[workspaceId]/maps/components/maps-feed-layer-form';
import { DEFAULT_LAYER_GROUP, layoutGroup } from '@/app/workspace/[workspaceId]/maps/lib/maps-layer-groups';
import {
  mapsLayerPath, mapsPath, mapsSettingsLegacyPath, mapsSettingsPath,
} from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { mapsDeploymentRestrictsLayerCatalog } from '@/app/workspace/[workspaceId]/maps/lib/maps-deployment';
import { useMapLayers } from '@/app/workspace/[workspaceId]/maps/lib/use-map-layouts';
import { feedVisibilityRows, type FeedSource } from '@/app/workspace/[workspaceId]/maps/lib/maps-feed-visibility';
import { resolveMapsPinImageUrl } from '@/app/workspace/[workspaceId]/maps/lib/maps-pin-image-url';
import { MapsSettingsBasemapsSection } from '@/app/workspace/[workspaceId]/maps/components/maps-settings-basemaps-section';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { BulkBar, SelectAllCell, SelectRowCell, onOffActions, useRowSelection } from '@/components/settings/bulk-access';
import {
  EVERY_FEATURE, FEED_COLUMNS, FEED_EXPORT_HEADERS, LAYER_COLUMNS, feedCellValues, feedExportRow, feedSearchTexts,
  feedSortValue, layerCellValues, layerSearchTexts, layerSortValue, mapsFeedEntries, mapsLayerEntries,
} from './maps-settings-model';

const NEW = 'new';
/** The batch actions of the feeds table, and of a feed's layers. */
const FEED_ACTIONS = onOffActions({ on: 'Enable', off: 'Disable' }, (on, count) =>
  on
    ? `Their layers come back in Maps for every member of this workspace, in one save.`
    : `Their layers disappear from Maps for every member of this workspace (${count === 1 ? 'it' : 'they'} can be enabled again here), in one save.`
);
const LAYER_ACTIONS = onOffActions({ on: 'Show', off: 'Hide' }, (on) =>
  on ? 'They come back in Maps for every member of this workspace.' : 'They disappear from Maps for every member of this workspace.'
);
const SEEDED_FEED_HINT = 'Provided by the deployment: hide its layers, or narrow its Access, instead of deleting it';
const SEEDED_LAYER_HINT = 'Provided by the deployment: hide it instead of deleting it';
const LAST_LAYER_HINT = 'A feed needs at least one layer: delete the feed instead';

/**
 * Settings → Maps at one place: the overview, a feed's page (`feed`, `maps/feeds/<id>`) or a
 * layer's page (`layer`, `maps/layers/<id>`), `new` for one to create. Each route renders it.
 */
export function MapsSettingsView({ feed = null, layer = null }: { feed?: string | null; layer?: string | null }) {
  return <Suspense fallback={null}><MapsSettings selectedFeed={feed} selectedLayer={layer} /></Suspense>;
}

/** An instance's kind beside its name (Seeded layer, API feed, Draft). */
function KindBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex shrink-0 items-center bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary" data-instance-kind="">
      {children}
    </span>
  );
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof LayoutApiError && error.errors.length) return error.errors.join('\n');
  return error instanceof Error ? error.message : fallback;
}

function feedTypeLabel(feed: WorkspaceMapLayout): FeedSource {
  if (isStoredFeed(feed)) return 'Stored feed';
  return isFeedLayout(feed) ? 'API feed' : 'SPARQL feed';
}

/** Why a feed layer cannot be deleted, or null when it can. */
function layerDeleteBlock(layer: WorkspaceFeedLayer, siblings: number): string | null {
  if (layer.shared_from) return 'Shared from another workspace';
  if (layer.system) return SEEDED_LAYER_HINT;
  if (siblings <= 1) return LAST_LAYER_HINT;
  return null;
}

function MapsSettings({ selectedFeed, selectedLayer }: { selectedFeed: string | null; selectedLayer: string | null }) {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const search = useSearchParams();
  const forFeed = search?.get('for') ?? undefined;
  // A former link (`?feed=`, `?layer=`) opens the page it names.
  const legacy = !selectedFeed && !selectedLayer ? mapsSettingsLegacyPath(workspaceId, search) : null;
  useEffect(() => {
    if (legacy) router.replace(legacy);
  }, [legacy, router]);
  const {
    all, hidden, hiddenFeeds, canEdit, workspaceLayouts: feeds, feedLayers, loading, error, layerGroups,
  } = useMapLayers();
  const applyLayouts = useMapsStore((s) => s.applyLayouts);
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [tableError, setTableError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const permissions = useMapsPermissions(workspaceId, canEdit);
  const { confirm, dialog: confirmDialog } = useConfirm();

  // Fresh from the server whenever the page opens.
  useEffect(() => { if (workspaceId) void loadLayouts(workspaceId, true); }, [workspaceId, loadLayouts]);

  const go = (options: Parameters<typeof mapsSettingsPath>[1]) =>
    router.push(mapsSettingsPath(workspaceId, options), { scroll: false });
  const reload = () => loadLayouts(workspaceId, true);

  const layersByFeed = useMemo(() => {
    const map = new Map<string, WorkspaceFeedLayer[]>();
    for (const layer of feedLayers) map.set(layer.feed_id, [...(map.get(layer.feed_id) ?? []), layer]);
    return map;
  }, [feedLayers]);
  const layerRecord = (id: string) => feedLayers.find((layer) => layer.id === id) ?? null;
  const takenLayerIds = useMemo(() => new Set(all.map((e) => e.id)), [all]);

  // A table of switches: each change saved at once, and said (`done`).
  const run = async (id: string, action: () => Promise<unknown>, failure: string, done?: string) => {
    setBusyId(id); setTableError(null); setNotice('');
    try {
      await action();
      if (done) setNotice(done);
    } catch (e) {
      setTableError(errorText(e, failure));
    } finally { setBusyId(null); }
  };

  const toggleShown = (layer: WorkspaceFeedLayer) => run(layer.id, async () => {
    const result = await layoutsApi.setHidden(workspaceId, layer.id, !hidden.includes(layer.id));
    applyLayouts(workspaceId, { hidden: result.hidden });
  }, 'Could not change the layer', `${layer.title} ${hidden.includes(layer.id) ? 'shown' : 'hidden'}.`);

  const toggleFeedShown = (feedId: string, title: string) => run(`feed:${feedId}`, async () => {
    const result = await layoutsApi.setFeedHidden(workspaceId, feedId, !hiddenFeeds.includes(feedId));
    applyLayouts(workspaceId, { hiddenFeeds: result.hidden_feeds });
  }, 'Could not change the feed', `${title} ${hiddenFeeds.includes(feedId) ? 'enabled' : 'disabled'}.`);

  /** Show or hide `layers` (a feed's, selected), those that would change, one after the other. */
  const setLayersShown = (layers: WorkspaceFeedLayer[], shown: boolean) => {
    const changing = layers.filter((layer) => hidden.includes(layer.id) === shown);
    return run('layer:bulk', async () => {
      for (const layer of changing) {
        const result = await layoutsApi.setHidden(workspaceId, layer.id, !shown);
        applyLayouts(workspaceId, { hidden: result.hidden });
      }
    }, `Could not ${shown ? 'show' : 'hide'} the layers`, `${changing.length} layer${changing.length === 1 ? '' : 's'} ${shown ? 'shown' : 'hidden'}.`);
  };

  const setLayerColor = (layer: WorkspaceFeedLayer, color: string) => run(layer.id, async () => {
    const saved = await feedLayersApi.save(workspaceId, layer.id, { ...feedLayerDraft(layer), color });
    applyLayouts(workspaceId, { feedLayers: feedLayers.map((l) => (l.id === saved.id ? saved : l)) });
  }, 'Could not change the layer color');

  const deleteLayer = async (layer: WorkspaceFeedLayer) => {
    const ok = await confirm({
      title: `Delete the layer “${layer.title}”?`,
      description: 'It is removed from Maps for every member of this workspace. Its feed stays.',
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!ok) return;
    await run(layer.id, async () => {
      await feedLayersApi.remove(workspaceId, layer.id);
      await reload();
      if (selectedLayer === layer.id) go({});
    }, 'Could not delete the layer');
  };

  const deleteFeed = async (feed: WorkspaceMapLayout) => {
    const count = layersByFeed.get(feed.id)?.length ?? 0;
    const ok = await confirm({
      title: `Delete the feed “${feed.title}”?`,
      description: `Its ${count} layer${count === 1 ? '' : 's'} go with it, for every member of this workspace.`,
      confirmLabel: 'Delete',
      destructive: true,
    });
    if (!ok) return;
    await run(feed.id, async () => {
      await layoutsApi.remove(workspaceId, feed.id);
      await reload();
      if (selectedFeed === feed.id) go({});
    }, 'Could not delete the feed');
  };

  const catalogRestricted = mapsDeploymentRestrictsLayerCatalog();
  const ownFeeds = feeds.filter((feed) => !feed.shared_from);
  const backBar = <InstanceBack href={mapsSettingsPath(workspaceId)} label="Maps" />;

  // ── Overview rows (read before an item's page returns: the table's hook comes first) ──
  const feedsById = new Map(feeds.map((feed) => [feed.id, feed]));
  // Every feed with its layers (records, built-ins, graph layers); a record whose layers are not
  // listed yet still gets its row. Deployment feeds this workspace may not use (e.g. set to "No
  // workspace") are listed after them, so their access can be given back.
  const { data: accessData, find: findAccess, names: accessNames } = permissions;
  const feedEntries = useMemo(() => {
    const rows = feedVisibilityRows(all, hiddenFeeds);
    for (const feed of feeds) {
      if (rows.some((row) => row.id === feed.id)) continue;
      rows.push({
        id: feed.id,
        title: feed.title,
        group: layoutGroup(feed),
        source: feedTypeLabel(feed),
        layers: layersByFeed.get(feed.id)?.length ?? 0,
        shown: !hiddenFeeds.includes(feed.id),
        logoUrl: feed.logo_url,
      });
    }
    const unavailable = (accessData?.items ?? []).filter(
      (item) => item.kind === 'layout' && item.owner === '' && !feeds.some((feed) => feed.id === item.item_id),
    );
    return mapsFeedEntries({
      rows,
      unavailable,
      feedIds: new Set(feeds.map((feed) => feed.id)),
      canEdit,
      find: (itemId) => findAccess('layout', itemId),
      names: accessNames,
    });
  }, [all, hiddenFeeds, feeds, layersByFeed, accessData, findAccess, accessNames, canEdit]);
  // A page at a time: the search and the column filters reach every feed, and a change of them
  // goes back to the first page.
  const feedTable = useSettingsTable({
    rows: feedEntries,
    columns: FEED_COLUMNS,
    cellValues: feedCellValues,
    searchTexts: feedSearchTexts,
    sortValue: feedSortValue,
    initialSort: 'group',
  });
  // The feeds checked for a batch change (the rows shown: select all takes those that switch).
  const feedSelection = useRowSelection(useMemo(() => feedTable.shown.map((entry) => entry.id), [feedTable.shown]));
  const bulkBusy = busyId === 'feed:bulk';
  /** The selected feeds an action fits: a feed of the workspace (not one it may not use). */
  const selectedFeeds = () => feedEntries.filter((entry) => feedSelection.selected.has(entry.id) && entry.row);
  /** Enable or disable every selected feed that would change, in one write. */
  const applyFeedsBulk = async (id: string) => {
    const on = id === 'on';
    const ids = selectedFeeds().filter((entry) => entry.shown !== on).map((entry) => entry.id);
    await run('feed:bulk', async () => {
      if (ids.length === 0) return;
      const result = await layoutsApi.setFeedsHidden(workspaceId, ids, !on);
      applyLayouts(workspaceId, { hiddenFeeds: result.hidden_feeds });
    }, `Could not ${on ? 'enable' : 'disable'} the feeds`, `${ids.length} feed${ids.length === 1 ? '' : 's'} ${on ? 'enabled' : 'disabled'}.`);
  };
  const exportFeeds = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(FEED_EXPORT_HEADERS, feedTable.shown.map(feedExportRow), format, `map_feeds_${date}`, 'Feeds');
  };

  // ── One feed ──────────────────────────────────────────────────────────────
  if (selectedFeed) {
    const creating = selectedFeed === NEW;
    if (catalogRestricted && creating) { go({}); return null; }
    const feed = creating ? null : feeds.find((f) => f.id === selectedFeed) ?? null;
    return (
      <div className="space-y-6">
        {confirmDialog}
        {backBar}
        {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
        {notice && <p className="text-xs text-muted-foreground" role="status" data-maps-notice="">{notice}</p>}
        {loading && !creating && !feed ? (
          <SettingsLoading />
        ) : !creating && !feed ? (
          <SettingsEmpty title={<>There is no feed “{selectedFeed}”.</>} />
        ) : (
          <FeedPage
            key={selectedFeed}
            workspaceId={workspaceId}
            feed={feed}
            layers={feed ? layersByFeed.get(feed.id) ?? [] : []}
            takenIds={takenLayerIds}
            canEdit={canEdit}
            layerGroups={layerGroups}
            busyId={busyId}
            onSavedGeoJson={(layerId) => router.push(mapsLayerPath(workspaceId, layerId))}
            onSaved={async (saved) => {
              await reload();
              if (creating) go({ feed: saved.id });
            }}
            onDelete={(f) => void deleteFeed(f)}
            onEditLayer={(id) => go({ layer: id })}
            onNewLayer={(feedId) => go({ layer: NEW, forFeed: feedId })}
            onDeleteLayer={(layer) => void deleteLayer(layer)}
            onLayersChanged={reload}
            hidden={hidden}
            onToggleShown={(layer) => void toggleShown(layer)}
            onSetShown={setLayersShown}
            onColor={(layer, color) => void setLayerColor(layer, color)}
          />
        )}
      </div>
    );
  }

  // ── One layer ─────────────────────────────────────────────────────────────
  if (selectedLayer) {
    const creating = selectedLayer === NEW;
    const layer = creating ? null : layerRecord(selectedLayer);
    const siblings = layer ? layersByFeed.get(layer.feed_id)?.length ?? 0 : 0;
    const feed = layer ? feeds.find((f) => f.id === layer.feed_id) : undefined;
    const block = layer ? layerDeleteBlock(layer, siblings) : null;
    return (
      <div className="space-y-6">
        {confirmDialog}
        {backBar}
        {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
        {loading && !creating && !layer ? (
          <SettingsLoading />
        ) : !creating && !layer ? (
          <SettingsEmpty title={<>There is no editable layer “{selectedLayer}”. Built-in and graph layers are hidden or recolored from the table.</>} />
        ) : (
          <>
            <InstanceHeader
              name={layer ? layer.title : 'New layer'}
              id={layer ? layer.id : null}
              badge={<KindBadge>{layer ? (layer.system ? 'Seeded layer' : 'Layer') : 'Draft'}</KindBadge>}
              meta={
                layer
                  ? `A view on the feed “${feed?.title ?? layer.feed_id}”.${layer.shared_from ? ' Shared from another workspace: read-only here.' : ''}`
                  : 'Draws a feed: every feature, or the feature types you pick.'
              }
              actions={
                layer ? (
                  <>
                    {feed && (
                      <Button variant="secondary" onClick={() => go({ feed: feed.id })}>
                        Feed: {feed.title}
                      </Button>
                    )}
                    <Button variant="secondary" onClick={() => window.open(mapsLayerPath(workspaceId, layer.id), '_self')}>
                      <MapIcon size={16} /> Open in Maps
                    </Button>
                    {canEdit && (
                      <Button
                        variant="destructive-ghost"
                        onClick={() => void deleteLayer(layer)}
                        disabled={Boolean(block) || busyId === layer.id}
                        title={block ?? undefined}
                      >
                        <Trash2 size={16} /> Delete
                      </Button>
                    )}
                  </>
                ) : undefined
              }
            />
            {!canEdit && <SettingsNotice>Only workspace owners and admins can edit layers.</SettingsNotice>}
            <SettingsSection title="Layer">
              <MapsFeedLayerForm
                key={selectedLayer}
                workspaceId={workspaceId}
                layer={layer}
                feeds={layer ? feeds.filter((f) => f.id === layer.feed_id) : ownFeeds}
                initialFeedId={forFeed}
                takenIds={takenLayerIds}
                canEdit={canEdit}
                onSaved={async (saved) => {
                  await reload();
                  if (creating) go({ layer: saved.id });
                }}
              />
            </SettingsSection>
          </>
        )}
      </div>
    );
  }

  // ── Overview ──────────────────────────────────────────────────────────────
  return (
    <div className="min-w-0 space-y-6">
      {confirmDialog}
      <SettingsPageHeader
        title="Maps"
        // One total: how many feeds (the Enabled column says which are shown).
        badge={`${feedEntries.length} feed${feedEntries.length === 1 ? '' : 's'}`}
        description={`${WORKSPACE_PAGE_DESCRIPTIONS['/settings/maps']}. A hidden layer is hidden for every member`}
        actions={
          <>
            <UsersExportMenu onExport={exportFeeds} disabled={feedTable.shown.length === 0} />
            {catalogRestricted ? null : (
              <>
                <Button variant="secondary" onClick={() => go({ feed: NEW })}>
                  <Plus size={16} /> New feed
                </Button>
                <Button onClick={() => go({ layer: NEW })} disabled={ownFeeds.length === 0}>
                  <Plus size={16} /> New layer
                </Button>
              </>
            )}
          </>
        }
      />

      {error && <SettingsNotice tone="error"><span role="alert">{error}</span></SettingsNotice>}
      {permissions.error && <SettingsNotice tone="error"><span role="alert">{permissions.error}</span></SettingsNotice>}
      {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
      {notice && <p className="text-xs text-muted-foreground" role="status" data-maps-notice="">{notice}</p>}
      {!canEdit && !loading && <SettingsNotice>Only workspace owners and admins can change feeds and layers.</SettingsNotice>}

      <SettingsSection
        title="Feed Layers"
        description="Each row is a feed (data source) and the layers drawn from it. Open a feed to edit its layers; switch it off to hide all its layers for every member of this workspace. Built-in feeds (Environment, SIGINT, Situation) are listed with the others."
      >
        <SettingsTableToolbar
          className="mb-3"
          search={feedTable.search}
          onSearchChange={feedTable.setSearch}
          searchPlaceholder="Search feeds…"
          // No count above the search: the badge says how many, the pager how many are shown.
          meta={<SettingsTableClear table={feedTable} />}
        />
        {canEdit && (
          <div className="mb-3">
            <BulkBar
              selection={feedSelection}
              noun="feed"
              actions={FEED_ACTIONS}
              onApply={applyFeedsBulk}
              skippedFor={() => feedSelection.selected.size - selectedFeeds().length}
              change="this change"
              disabled={bulkBusy}
            />
          </div>
        )}
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table table-fixed">
            <SettingsTableHead
              table={feedTable}
              leading={
                <SelectAllCell
                  selection={feedSelection}
                  keys={feedTable.shown.filter((entry) => entry.row).map((entry) => entry.id)}
                  noun="feed"
                  disabled={!canEdit || bulkBusy}
                />
              }
              trailing={<th className="w-24" aria-label="Actions" />}
            />
            <tbody>
              {loading && !feedEntries.length && (
                <tr><td colSpan={FEED_COLUMNS.length + 2} className="text-muted-foreground"><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
              )}
              {!loading && feedEntries.length === 0 && (
                <tr><td colSpan={FEED_COLUMNS.length + 2} className="org-settings-users-no-match">No feeds yet</td></tr>
              )}
              {!loading && feedEntries.length > 0 && feedTable.shown.length === 0 && (
                <SettingsTableNoMatch colSpan={FEED_COLUMNS.length + 2} noun="feeds" />
              )}
              {feedTable.paged.pageRows.map(({ row, unavailable: item }) => {
                if (item) {
                  return (
                    <tr key={`unavailable:${item.item_id}`} data-feed={item.item_id}>
                      <SelectRowCell selection={feedSelection} rowKey={item.item_id} label={item.title} disabled />
                      <td className="max-w-0">
                        <div className="truncate font-medium text-muted-foreground" title={item.title}>{item.title}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          <span className="font-mono">{item.item_id}</span> · seeded · not available in this workspace
                        </div>
                      </td>
                      <td className="text-muted-foreground">—</td>
                      <td className="text-muted-foreground">—</td>
                      <td className="max-w-0 text-xs">
                        <MapsAccessCell workspaceId={workspaceId} kind="layout" itemId={item.item_id} permissions={permissions} />
                      </td>
                      <td className="text-muted-foreground">—</td>
                      <td />
                    </tr>
                  );
                }
                if (!row) return null;
                const feed = feedsById.get(row.id);
                const logo = resolveMapsPinImageUrl(row.logoUrl);
                const busy = busyId === `feed:${row.id}`;
                const editable = Boolean(feed && !feed.shared_from);
                return (
                  <tr
                    key={row.id}
                    data-feed={row.id}
                    onClick={feed ? () => go({ feed: feed.id }) : undefined}
                    className={cn(feed && 'cursor-pointer')}
                  >
                    <SelectRowCell selection={feedSelection} rowKey={row.id} label={row.title} disabled={!canEdit || bulkBusy} />
                    <td className="max-w-0">
                      <div className={cn('flex min-w-0 items-center gap-2', !row.shown && 'text-muted-foreground')}>
                        {logo ? (
                          // eslint-disable-next-line @next/next/no-img-element -- feed logo (API or https)
                          <img src={logo} alt="" width={14} height={14} className="shrink-0" />
                        ) : null}
                        <span className="truncate font-medium" title={row.title}>{row.title}</span>
                      </div>
                      <div className="truncate text-xs text-muted-foreground">
                        <span className="font-mono">{row.id}</span>
                        {' · '}{row.source}
                        {feed?.system ? ' · seeded' : ''}{feed?.shared_from ? ' · shared' : ''}
                      </div>
                    </td>
                    <td className="max-w-0 truncate text-muted-foreground" title={row.group}>{row.group}</td>
                    <td className="text-muted-foreground">{row.layers}</td>
                    <td className="max-w-0 text-xs" onClick={(e) => e.stopPropagation()}>
                      {feed && canEdit ? (
                        <MapsAccessCell workspaceId={workspaceId} kind="layout" itemId={feed.id} permissions={permissions} />
                      ) : (
                        <span className="text-muted-foreground" title={feed ? undefined : 'Built into Maps: available in every workspace'}>
                          {feed ? '—' : 'All workspaces'}
                        </span>
                      )}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <span className="inline-flex items-center gap-2">
                        <Checkbox
                          checked={row.shown}
                          disabled={!canEdit || busy}
                          onCheckedChange={() => void toggleFeedShown(row.id, row.title)}
                          aria-label={`${row.title} enabled`}
                        />
                        {busy && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
                      </span>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {feed ? (
                        <span className="inline-flex items-center gap-1">
                          <Button variant="ghost" size="icon" onClick={() => go({ feed: feed.id })} aria-label={`Edit ${feed.title}`} title={canEdit ? 'Edit' : 'View'}>
                            <Pencil size={14} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={!canEdit || !editable || feed.system || busyId === feed.id}
                            onClick={() => void deleteFeed(feed)}
                            aria-label={`Delete ${feed.title}`}
                            title={feed.system ? SEEDED_FEED_HINT : !editable ? 'Shared from another workspace' : 'Delete the feed and its layers'}
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
        <TablePager total={feedTable.shown.length} paged={feedTable.paged} />
      </SettingsSection>

      <MapsSettingsBasemapsSection workspaceId={workspaceId} canEdit={canEdit} permissions={permissions} />
    </div>
  );
}

function FeedPage({
  workspaceId,
  feed,
  layers,
  takenIds,
  canEdit,
  layerGroups,
  busyId,
  onSaved,
  onSavedGeoJson,
  onDelete,
  onEditLayer,
  onNewLayer,
  onDeleteLayer,
  onLayersChanged,
  hidden,
  onToggleShown,
  onSetShown,
  onColor,
}: {
  workspaceId: string;
  feed: WorkspaceMapLayout | null;
  layers: WorkspaceFeedLayer[];
  takenIds: Set<string>;
  canEdit: boolean;
  layerGroups: readonly string[];
  busyId: string | null;
  onSaved: (feed: WorkspaceMapLayout) => void;
  onSavedGeoJson: (layerId: string) => void;
  onDelete: (feed: WorkspaceMapLayout) => void;
  onEditLayer: (layerId: string) => void;
  onNewLayer: (feedId: string) => void;
  onDeleteLayer: (layer: WorkspaceFeedLayer) => void;
  onLayersChanged: () => Promise<void>;
  hidden: string[];
  onToggleShown: (layer: WorkspaceFeedLayer) => void;
  /** Show or hide the layers selected, asked first. */
  onSetShown: (layers: WorkspaceFeedLayer[], shown: boolean) => Promise<void>;
  onColor: (layer: WorkspaceFeedLayer, color: string) => void;
}) {
  const isNew = feed === null;
  const shared = Boolean(feed?.shared_from);
  const { types } = useFeedTypes(workspaceId, feed);
  const [adding, setAdding] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const layerRows = useMemo(() => mapsLayerEntries(layers, hidden), [layers, hidden]);
  const layerTable = useSettingsTable({
    rows: layerRows,
    columns: LAYER_COLUMNS,
    cellValues: layerCellValues,
    searchTexts: layerSearchTexts,
    sortValue: layerSortValue,
    initialSort: 'order',
  });
  // The layers checked for a batch change (the rows shown: select all takes them).
  const layerSelection = useRowSelection(useMemo(() => layerTable.shown.map((layer) => layer.id), [layerTable.shown]));
  const layerBusy = busyId === 'layer:bulk';

  // Feature types no layer of this feed lists yet (a layer with no types already shows them all).
  const covered = new Set(layers.flatMap((layer) => layer.class_labels));
  const showsAll = layers.some((layer) => layer.class_labels.length === 0);
  const uncovered = (types ?? []).filter((t) => !covered.has(t.label));

  const addTypeLayer = async (label: string) => {
    if (!feed) return;
    setAdding(label); setAddError(null);
    let id = slugifyLayerId(`${feed.id}-${label}`);
    for (let n = 2; takenIds.has(id); n += 1) id = slugifyLayerId(`${feed.id}-${label}-${n}`);
    try {
      await feedLayersApi.save(workspaceId, id, {
        feed_id: feed.id,
        title: label,
        description: '',
        color: feed.color,
        icon: facilityClassIcon(label) ?? '',
        order: 100 + layers.length,
        class_labels: [label],
      });
      await onLayersChanged();
    } catch (e) {
      setAddError(errorText(e, 'Could not add the layer'));
    } finally { setAdding(null); }
  };

  const initialGroup = feed ? layoutGroup(feed) : DEFAULT_LAYER_GROUP;

  return (
    <div className="space-y-6">
      <InstanceHeader
        name={feed ? feed.title : 'New feed'}
        id={feed ? feed.id : null}
        badge={<KindBadge>{feed ? `${feed.system ? 'Seeded ' : ''}${feedTypeLabel(feed)}` : 'Draft'}</KindBadge>}
        meta={
          isNew
            ? 'A data source: SPARQL over the workspace graphs, or a Nexus API path. It starts with one layer of every feature (GeoJSON: kept in this browser only).'
            : shared
              ? 'Shared from another workspace: read-only here.'
              : feed!.system
                ? 'Provided by this deployment: its availability is set in Access.'
                : 'Shared with every member of this workspace.'
        }
        actions={
          feed ? (
            <>
              <Button variant="secondary" onClick={() => window.open(mapsPath(workspaceId, layers.map((l) => l.id)), '_self')}>
                <MapIcon size={16} /> Open in Maps
              </Button>
              {canEdit && (
                <Button
                  variant="destructive-ghost"
                  onClick={() => onDelete(feed)}
                  disabled={feed.system || shared || busyId === feed.id}
                  title={feed.system ? SEEDED_FEED_HINT : shared ? 'Shared from another workspace' : 'Delete the feed and its layers'}
                >
                  <Trash2 size={16} /> Delete
                </Button>
              )}
            </>
          ) : undefined
        }
      />

      {!canEdit && <SettingsNotice>Only workspace owners and admins can edit feeds.</SettingsNotice>}

      <SettingsSection title="Feed">
        <MapsLayerEditorForm
          key={feed?.id ?? 'new'}
          variant="page"
          workspaceId={workspaceId}
          takenIds={takenIds}
          layerGroups={layerGroups}
          canEdit={canEdit && !shared}
          workspaceLayout={feed}
          initialGroup={initialGroup}
          initialSource="feed"
          onSavedWorkspace={onSaved}
          onSavedGeoJson={onSavedGeoJson}
        />
      </SettingsSection>

      {feed ? (
        <SettingsSection
          title="Layers"
          actions={canEdit && !shared ? (
            <Button variant="secondary" onClick={() => onNewLayer(feed.id)}>
              <Plus size={16} /> New layer
            </Button>
          ) : undefined}
        >
          <SettingsTableToolbar
            className="mb-3"
            search={layerTable.search}
            onSearchChange={layerTable.setSearch}
            searchPlaceholder="Search layers…"
            meta={<SettingsTableClear table={layerTable} />}
          />
          {canEdit && (
            <div className="mb-3">
              <BulkBar
                selection={layerSelection}
                noun="layer"
                actions={LAYER_ACTIONS}
                onApply={(id) => onSetShown(layers.filter((layer) => layerSelection.selected.has(layer.id)), id === 'on')}
                change="this change"
                disabled={layerBusy}
              />
            </div>
          )}
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table table-fixed">
              <SettingsTableHead
                table={layerTable}
                leading={
                  <SelectAllCell
                    selection={layerSelection}
                    keys={layerTable.shown.map((layer) => layer.id)}
                    noun="layer"
                    disabled={!canEdit || layerBusy}
                  />
                }
                trailing={canEdit ? <th className="w-24" aria-label="Actions" /> : undefined}
              />
              <tbody>
                {layerRows.length > 0 && layerTable.shown.length === 0 && (
                  <SettingsTableNoMatch colSpan={LAYER_COLUMNS.length + (canEdit ? 2 : 1)} noun="layers" />
                )}
                {layerTable.paged.pageRows.map((layer) => {
                  const Icon = mapsIconMap[layer.icon] ?? null;
                  const block = layerDeleteBlock(layer, layers.length);
                  return (
                    <tr key={layer.id} data-layer={layer.id} onClick={() => onEditLayer(layer.id)} className="cursor-pointer">
                      <SelectRowCell selection={layerSelection} rowKey={layer.id} label={layer.title} disabled={!canEdit || layerBusy} />
                      <td className="max-w-0">
                        <span className="inline-flex min-w-0 items-center gap-2">
                          <span className="flex h-6 w-6 shrink-0 items-center justify-center text-white" style={{ background: layer.color }}>
                            {Icon ? <Icon size={14} aria-hidden /> : null}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate font-medium">{layer.title}</span>
                            <span className="block truncate font-mono text-xs text-muted-foreground">{layer.id}{layer.system ? ' · seeded' : ''}</span>
                          </span>
                        </span>
                      </td>
                      <td className="max-w-0 truncate text-muted-foreground" title={layer.class_labels.join(', ')}>
                        {layer.class_labels.length ? layer.class_labels.join(', ') : EVERY_FEATURE}
                      </td>
                      <td className="text-muted-foreground">{layer.order}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        {canEdit && !shared ? (
                          <LayerColorInput
                            color={layer.color}
                            label={`${layer.title} color`}
                            title={layer.color}
                            onCommit={(next) => onColor(layer, next)}
                          />
                        ) : (
                          <span className="inline-block h-4 w-4 border border-border" style={{ background: layer.color }} aria-label={layer.color} />
                        )}
                      </td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <span className="inline-flex items-center gap-2">
                          <Checkbox
                            checked={layer.shown}
                            disabled={!canEdit || busyId === layer.id}
                            onCheckedChange={() => onToggleShown(layer)}
                            aria-label={`${layer.title} shown`}
                          />
                          {busyId === layer.id && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
                        </span>
                      </td>
                      {canEdit && (
                        <td onClick={(e) => e.stopPropagation()}>
                          <span className="inline-flex items-center gap-1">
                            <Button variant="ghost" size="icon" onClick={() => onEditLayer(layer.id)} aria-label={`Edit ${layer.title}`} title="Edit">
                              <Pencil size={14} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={Boolean(block) || busyId === layer.id}
                              onClick={() => onDeleteLayer(layer)}
                              aria-label={`Delete ${layer.title}`}
                              title={block ?? 'Delete'}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </span>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <TablePager total={layerTable.shown.length} paged={layerTable.paged} />

          {canEdit && !shared && hasFeatureTypes(feed) && uncovered.length > 0 ? (
            <div className="mt-4 space-y-2">
              <p className="text-sm text-muted-foreground">
                Feature types in this feed with no layer of their own
                {showsAll ? ' (an “every feature” layer still shows them)' : ''}:
              </p>
              {addError ? <SettingsNotice tone="error">{addError}</SettingsNotice> : null}
              <div className="flex flex-wrap gap-2">
                {uncovered.map((t) => (
                  <Button key={t.label} variant="secondary" size="sm" disabled={adding !== null} onClick={() => void addTypeLayer(t.label)}>
                    {adding === t.label ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                    {t.label} <span className="text-muted-foreground">({t.count})</span>
                  </Button>
                ))}
              </div>
            </div>
          ) : null}
        </SettingsSection>
      ) : null}
    </div>
  );
}

/** Color swatch that saves once the pick settles (the native input fires on every drag step). */
function LayerColorInput({
  color,
  label,
  title,
  onCommit,
}: {
  color: string;
  label: string;
  title: string;
  onCommit: (color: string) => void;
}) {
  const [value, setValue] = useState(color);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setValue(color), [color]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  return (
    <input
      type="color"
      className="h-6 w-8 cursor-pointer border border-border bg-transparent p-0"
      value={value}
      aria-label={label}
      title={title}
      onChange={(e) => {
        const next = e.target.value;
        setValue(next);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => { if (next !== color) onCommit(next); }, 400);
      }}
    />
  );
}
