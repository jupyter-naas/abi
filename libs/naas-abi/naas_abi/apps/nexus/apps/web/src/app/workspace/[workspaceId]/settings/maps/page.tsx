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
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, Loader2, Map as MapIcon, Pencil, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { SettingsReloadButton } from '@/components/settings/settings-reload';
import {
  SettingsEmpty, SettingsFilterSelect, SettingsLoading, SettingsNotice, SettingsPageHeader, SettingsSection,
  SettingsTableToolbar, countLabel, settingsTable,
} from '@/components/settings/settings-ui';
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
  mapsLayerPath, mapsPath, mapsSettingsPath, mapsSettingsSelectedFeed, mapsSettingsSelectedLayer,
} from '@/app/workspace/[workspaceId]/maps/lib/maps-route';
import { mapsDeploymentRestrictsLayerCatalog } from '@/app/workspace/[workspaceId]/maps/lib/maps-deployment';
import { useMapLayers } from '@/app/workspace/[workspaceId]/maps/lib/use-map-layouts';
import {
  feedVisibilityRows, filterFeedRows, type FeedSource, type FeedStatusFilter,
} from '@/app/workspace/[workspaceId]/maps/lib/maps-feed-visibility';
import { resolveMapsPinImageUrl } from '@/app/workspace/[workspaceId]/maps/lib/maps-pin-image-url';
import { MapsSettingsBasemapsSection } from '@/app/workspace/[workspaceId]/maps/components/maps-settings-basemaps-section';

const NEW = 'new';
const SEEDED_FEED_HINT = 'Provided by the deployment: hide its layers, or narrow its Access, instead of deleting it';
const SEEDED_LAYER_HINT = 'Provided by the deployment: hide it instead of deleting it';
const LAST_LAYER_HINT = 'A feed needs at least one layer: delete the feed instead';

export default function MapsSettingsPage() {
  return <Suspense fallback={null}><MapsSettings /></Suspense>;
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

function MapsSettings() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const search = useSearchParams();
  const selectedLayer = mapsSettingsSelectedLayer(search);
  const selectedFeed = mapsSettingsSelectedFeed(search);
  const forFeed = search?.get('for') ?? undefined;
  const {
    all, hidden, hiddenFeeds, canEdit, workspaceLayouts: feeds, feedLayers, loading, error, layerGroups,
  } = useMapLayers();
  const applyLayouts = useMapsStore((s) => s.applyLayouts);
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [tableError, setTableError] = useState<string | null>(null);
  // Feed Layers table search and filters.
  const [feedSearch, setFeedSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState<FeedStatusFilter>('all');
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

  const run = async (id: string, action: () => Promise<unknown>, failure: string) => {
    setBusyId(id); setTableError(null);
    try {
      await action();
    } catch (e) {
      setTableError(errorText(e, failure));
    } finally { setBusyId(null); }
  };

  const toggleShown = (layerId: string) => run(layerId, async () => {
    const result = await layoutsApi.setHidden(workspaceId, layerId, !hidden.includes(layerId));
    applyLayouts(workspaceId, { hidden: result.hidden });
  }, 'Could not change the layer');

  const toggleFeedShown = (feedId: string) => run(`feed:${feedId}`, async () => {
    const result = await layoutsApi.setFeedHidden(workspaceId, feedId, !hiddenFeeds.includes(feedId));
    applyLayouts(workspaceId, { hiddenFeeds: result.hidden_feeds });
  }, 'Could not change the feed');

  /** Enable or disable every feed the search and filters list. */
  const setListedFeedsShown = async (ids: string[], shown: boolean) => {
    if (!ids.length) return;
    const ok = await confirm({
      title: `${shown ? 'Enable' : 'Disable'} ${ids.length} feed${ids.length === 1 ? '' : 's'}?`,
      description: shown
        ? 'Their layers come back in Maps for every member of this workspace.'
        : 'Their layers disappear from Maps for every member of this workspace. You can enable them again here.',
      confirmLabel: shown ? 'Enable' : 'Disable',
      destructive: !shown,
    });
    if (!ok) return;
    await run('feed:bulk', async () => {
      const result = await layoutsApi.setFeedsHidden(workspaceId, ids, !shown);
      applyLayouts(workspaceId, { hiddenFeeds: result.hidden_feeds });
    }, `Could not ${shown ? 'enable' : 'disable'} the feeds`);
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
  const backBar = (
    <div className="flex items-center justify-between gap-2">
      <Button variant="secondary" onClick={() => go({})}>
        <ArrowLeft size={16} /> Maps settings
      </Button>
      <SettingsReloadButton />
    </div>
  );

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
            onToggleShown={(layer) => void toggleShown(layer.id)}
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
            <SettingsPageHeader
              title={layer ? layer.title : 'New layer'}
              badge={layer ? (layer.system ? 'Seeded layer' : 'Layer') : 'Draft'}
              description={
                layer
                  ? `A view on the feed “${feed?.title ?? layer.feed_id}”.${layer.shared_from ? ' Shared from another workspace: read-only here.' : ''}`
                  : 'A layer draws from a feed: every feature, or only the feature types you pick.'
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
  const shownCount = all.filter(
    (e) => !hidden.includes(e.id) && !hiddenFeeds.includes(e.feedId ?? e.id),
  ).length;
  const feedsById = new Map(feeds.map((feed) => [feed.id, feed]));
  // Every feed with its layers (records, built-ins, graph layers); a record
  // whose layers are not listed yet still gets its row.
  const feedRows = feedVisibilityRows(all, hiddenFeeds);
  for (const feed of feeds) {
    if (feedRows.some((row) => row.id === feed.id)) continue;
    feedRows.push({
      id: feed.id,
      title: feed.title,
      group: layoutGroup(feed),
      source: feedTypeLabel(feed),
      layers: layersByFeed.get(feed.id)?.length ?? 0,
      shown: !hiddenFeeds.includes(feed.id),
      logoUrl: feed.logo_url,
    });
  }
  // Deployment feeds this workspace may not use (e.g. set to "No workspace"):
  // listed so their access can be given back.
  const unavailableFeeds = (permissions.data?.items ?? []).filter(
    (item) => item.kind === 'layout' && item.owner === '' && !feeds.some((feed) => feed.id === item.item_id),
  );
  const feedFilter = { search: feedSearch, group: groupFilter, status: statusFilter };
  const listedFeedRows = filterFeedRows(feedRows, feedFilter);
  // Unavailable feeds count as disabled and belong to no group.
  const listedUnavailable = filterFeedRows(
    unavailableFeeds.map((item) => ({
      item, id: item.item_id, title: item.title, group: '', source: 'API feed' as FeedSource, shown: false,
    })),
    feedFilter,
  ).map(({ item }) => item);
  const groupOptions = [...new Map(feedRows.map((row) => [row.group.toLowerCase(), row.group])).values()];
  const feedTotal = feedRows.length + unavailableFeeds.length;
  // Bulk actions apply to the listed feeds that would change.
  const listedOff = listedFeedRows.filter((row) => !row.shown).map((row) => row.id);
  const listedOn = listedFeedRows.filter((row) => row.shown).map((row) => row.id);
  const bulkBusy = busyId === 'feed:bulk';
  const feedListed = listedFeedRows.length + listedUnavailable.length;

  return (
    <div className="min-w-0 space-y-6">
      {confirmDialog}
      <SettingsPageHeader
        title="Maps"
        badge={`${shownCount} shown`}
        description="Feeds are data sources; layers are what Maps lists and draws, each a view on one feed. Hidden layers disappear for every member of the workspace."
        actions={
          catalogRestricted ? undefined : (
            <>
              <Button variant="secondary" onClick={() => go({ feed: NEW })}>
                <Plus size={16} /> New feed
              </Button>
              <Button onClick={() => go({ layer: NEW })} disabled={ownFeeds.length === 0}>
                <Plus size={16} /> New layer
              </Button>
            </>
          )
        }
      />

      {error && <SettingsNotice tone="error"><span role="alert">{error}</span></SettingsNotice>}
      {permissions.error && <SettingsNotice tone="error"><span role="alert">{permissions.error}</span></SettingsNotice>}
      {tableError && <SettingsNotice tone="error"><span role="alert" className="whitespace-pre-line">{tableError}</span></SettingsNotice>}
      {!canEdit && !loading && <SettingsNotice>Only workspace owners and admins can change feeds and layers.</SettingsNotice>}

      <SettingsSection
        title="Feed Layers"
        description="Each row is a feed (data source) and the layers drawn from it. Open a feed to edit its layers; switch it off to hide all its layers for every member of this workspace. Built-in feeds (Environment, SIGINT, Situation) are listed with the others."
      >
        <SettingsTableToolbar
          className="mb-3"
          search={feedSearch}
          onSearchChange={setFeedSearch}
          searchPlaceholder="Search feeds…"
          filters={
            <>
              <SettingsFilterSelect
                label="Group"
                value={groupFilter}
                onChange={setGroupFilter}
                options={[
                  { value: 'all', label: 'All groups' },
                  ...groupOptions.map((group) => ({ value: group, label: group })),
                ]}
              />
              <SettingsFilterSelect
                label="Status"
                value={statusFilter}
                onChange={(value) => setStatusFilter(value as FeedStatusFilter)}
                options={[
                  { value: 'all', label: 'All statuses' },
                  { value: 'enabled', label: 'Enabled' },
                  { value: 'disabled', label: 'Disabled' },
                ]}
              />
              {canEdit && (
                <>
                  <Button
                    variant="secondary"
                    disabled={bulkBusy || listedOff.length === 0}
                    onClick={() => void setListedFeedsShown(listedOff, true)}
                    title="Enable every listed feed that is disabled"
                  >
                    {bulkBusy ? <Loader2 size={14} className="animate-spin" /> : null}
                    Enable{listedOff.length ? ` (${listedOff.length})` : ''}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={bulkBusy || listedOn.length === 0}
                    onClick={() => void setListedFeedsShown(listedOn, false)}
                    title="Disable every listed feed that is enabled"
                  >
                    Disable{listedOn.length ? ` (${listedOn.length})` : ''}
                  </Button>
                </>
              )}
            </>
          }
          meta={countLabel(feedListed, feedTotal, 'feed')}
        />
        <div className="overflow-x-hidden border border-border bg-card">
          <table className={cn(settingsTable.table, 'table-fixed')}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Name</th>
                <th className={cn(settingsTable.th, 'w-44')}>Group</th>
                <th className={cn(settingsTable.th, 'w-20')}>Layers</th>
                <th className={cn(settingsTable.th, 'w-44')}>Access</th>
                <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
                <th className={cn(settingsTable.th, 'w-24')} aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {loading && !feedRows.length && (
                <tr><td colSpan={6} className={cn(settingsTable.td, 'text-muted-foreground')}><Loader2 size={14} className="mr-2 inline animate-spin" />Loading…</td></tr>
              )}
              {!loading && feedTotal === 0 && (
                <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">No feeds yet</td></tr>
              )}
              {!loading && feedTotal > 0 && feedListed === 0 && (
                <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">No feeds match these filters</td></tr>
              )}
              {listedFeedRows.map((row) => {
                const feed = feedsById.get(row.id);
                const logo = resolveMapsPinImageUrl(row.logoUrl);
                const busy = busyId === `feed:${row.id}`;
                const editable = Boolean(feed && !feed.shared_from);
                return (
                  <tr
                    key={row.id}
                    onClick={feed ? () => go({ feed: feed.id }) : undefined}
                    className={cn(settingsTable.row, feed && 'cursor-pointer')}
                  >
                    <td className={cn(settingsTable.td, 'max-w-0')}>
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
                    <td className={cn(settingsTable.td, 'max-w-0 truncate text-muted-foreground')} title={row.group}>{row.group}</td>
                    <td className={cn(settingsTable.td, 'text-muted-foreground')}>{row.layers}</td>
                    <td className={cn(settingsTable.td, 'max-w-0 text-xs')} onClick={(e) => e.stopPropagation()}>
                      {feed && canEdit ? (
                        <MapsAccessCell workspaceId={workspaceId} kind="layout" itemId={feed.id} permissions={permissions} />
                      ) : (
                        <span className="text-muted-foreground" title={feed ? undefined : 'Built into Maps: available in every workspace'}>
                          {feed ? '—' : 'All workspaces'}
                        </span>
                      )}
                    </td>
                    <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                      <span className="inline-flex items-center gap-2">
                        <Checkbox
                          checked={row.shown}
                          disabled={!canEdit || busy}
                          onCheckedChange={() => void toggleFeedShown(row.id)}
                          aria-label={`${row.title} enabled`}
                        />
                        {busy && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
                      </span>
                    </td>
                    <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
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
              {listedUnavailable.map((item) => (
                <tr key={`unavailable:${item.item_id}`} className={settingsTable.row}>
                  <td className={cn(settingsTable.td, 'max-w-0')}>
                    <div className="truncate font-medium text-muted-foreground" title={item.title}>{item.title}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      <span className="font-mono">{item.item_id}</span> · seeded · not available in this workspace
                    </div>
                  </td>
                  <td className={cn(settingsTable.td, 'text-muted-foreground')}>—</td>
                  <td className={cn(settingsTable.td, 'text-muted-foreground')}>—</td>
                  <td className={cn(settingsTable.td, 'max-w-0 text-xs')}>
                    <MapsAccessCell workspaceId={workspaceId} kind="layout" itemId={item.item_id} permissions={permissions} />
                  </td>
                  <td className={cn(settingsTable.td, 'text-muted-foreground')}>—</td>
                  <td className={settingsTable.td} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
  onColor: (layer: WorkspaceFeedLayer, color: string) => void;
}) {
  const isNew = feed === null;
  const shared = Boolean(feed?.shared_from);
  const { types } = useFeedTypes(workspaceId, feed);
  const [adding, setAdding] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const sortedLayers = [...layers].sort((a, b) => a.order - b.order || a.title.localeCompare(b.title));

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
      <SettingsPageHeader
        title={feed ? feed.title : 'New feed'}
        badge={feed ? `${feed.system ? 'Seeded ' : ''}${feedTypeLabel(feed)}` : 'Draft'}
        description={
          isNew
            ? 'A feed is a data source: SPARQL over the workspace graphs or a Nexus API path. It starts with one layer showing every feature; add layers for its feature types below. (GeoJSON makes a layer kept in this browser only.)'
            : shared
              ? 'Shared from another workspace: read-only here.'
              : feed!.system
                ? 'Provided by this deployment: edit it and its layers; its availability is set in Access.'
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
          <div className="overflow-x-hidden border border-border bg-card">
            <table className={cn(settingsTable.table, 'table-fixed')}>
              <thead>
                <tr className={settingsTable.headRow}>
                  <th className={settingsTable.th}>Layer</th>
                  <th className={settingsTable.th}>Feature types</th>
                  <th className={cn(settingsTable.th, 'w-16')}>Order</th>
                  <th className={cn(settingsTable.th, 'w-16')}>Color</th>
                  <th className={cn(settingsTable.th, 'w-20')}>Shown</th>
                  {canEdit && <th className={cn(settingsTable.th, 'w-24')} aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {sortedLayers.map((layer) => {
                  const Icon = mapsIconMap[layer.icon] ?? null;
                  const block = layerDeleteBlock(layer, layers.length);
                  return (
                    <tr key={layer.id} onClick={() => onEditLayer(layer.id)} className={cn(settingsTable.row, 'cursor-pointer')}>
                      <td className={cn(settingsTable.td, 'max-w-0')}>
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
                      <td className={cn(settingsTable.td, 'max-w-0 truncate text-muted-foreground')} title={layer.class_labels.join(', ')}>
                        {layer.class_labels.length ? layer.class_labels.join(', ') : 'Every feature'}
                      </td>
                      <td className={cn(settingsTable.td, 'text-muted-foreground')}>{layer.order}</td>
                      <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
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
                      <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                        <span className="inline-flex items-center gap-2">
                          <Checkbox
                            checked={!hidden.includes(layer.id)}
                            disabled={!canEdit || busyId === layer.id}
                            onCheckedChange={() => onToggleShown(layer)}
                            aria-label={`${layer.title} shown`}
                          />
                          {busyId === layer.id && <Loader2 size={12} className="animate-spin text-muted-foreground" />}
                        </span>
                      </td>
                      {canEdit && (
                        <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
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
