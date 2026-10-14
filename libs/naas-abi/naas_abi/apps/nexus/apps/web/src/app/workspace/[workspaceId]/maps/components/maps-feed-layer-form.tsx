'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Select } from '@/components/ui/input';
import { SettingsNotice } from '@/components/settings/settings-ui';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { mapsCustomFeedUrl } from '../lib/datasets';
import {
  LayoutApiError,
  feedLayerDraft,
  feedLayersApi,
  type FeedLayerDraft,
} from '../lib/layouts-api';
import {
  hasFeatureTypes,
  isFeedLayout,
  isStoredFeed,
  type WorkspaceFeedLayer,
  type WorkspaceMapLayout,
} from '../lib/layouts';
import { useMapsStore, workspaceLayoutsOf } from '@/stores/maps';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { collectClassLabels } from '../lib/maps-layer-class-styles';
import { MapsIconGallery } from './maps-icon-gallery';

const ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,47}$/;

export function slugifyLayerId(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
}

/**
 * Feature types (pin classLabel) in a feed's live data, with counts. API feeds
 * only: SPARQL feeds have no feature types (every pin belongs to every layer).
 */
export function useFeedTypes(workspaceId: string, feed: WorkspaceMapLayout | null | undefined) {
  const [state, setState] = useState<{ types: { label: string; count: number }[] | null; error: string | null }>(
    { types: null, error: null },
  );
  // Stored feeds: read one of the feed's objects whole (`all`); API feeds: the feed.
  const storedLayerId = useMapsStore((s) => {
    if (!feed || !isStoredFeed(feed)) return null;
    const layers = workspaceLayoutsOf(s, workspaceId).feedLayers.filter(
      (layer) => layer.feed_id === feed.id && layer.storage_path,
    );
    return layers.sort((a, b) => a.order - b.order)[0]?.id ?? null;
  });
  const url = !feed || !workspaceId
    ? null
    : isFeedLayout(feed)
      ? mapsCustomFeedUrl(feed.id, workspaceId)
      : storedLayerId
        ? feedLayersApi.dataUrl(workspaceId, storedLayerId, { all: true })
        : null;
  useEffect(() => {
    if (!url) {
      setState({ types: [], error: null });
      return;
    }
    const controller = new AbortController();
    setState({ types: null, error: null });
    const token = useAuthStore.getState().token;
    fetchMapsFeedPins(url, controller.signal, {
      Authorization: `Bearer ${token ?? ''}`,
    })
      .then((result) => setState({ types: collectClassLabels(result.pins), error: null }))
      .catch((e: unknown) => {
        if (!controller.signal.aborted) {
          setState({ types: [], error: e instanceof Error ? e.message : 'Feed unavailable' });
        }
      });
    return () => controller.abort();
  }, [url]);
  return state;
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof LayoutApiError && error.errors.length) return error.errors.join('\n');
  return error instanceof Error ? error.message : fallback;
}

/** Settings → Maps layer editor: a view on one feed (title, feed, feature types, color, icon, order). */
export function MapsFeedLayerForm({
  workspaceId,
  layer,
  feeds,
  initialFeedId,
  takenIds,
  canEdit,
  onSaved,
}: {
  workspaceId: string;
  /** Null when creating. */
  layer: WorkspaceFeedLayer | null;
  /** Feeds the layer can draw from (this workspace's own). */
  feeds: WorkspaceMapLayout[];
  initialFeedId?: string;
  takenIds: ReadonlySet<string>;
  canEdit: boolean;
  onSaved: (layer: WorkspaceFeedLayer) => void;
}) {
  const isNew = layer === null;
  const startFeed = feeds.find((f) => f.id === (layer?.feed_id ?? initialFeedId)) ?? feeds[0];
  const [draft, setDraft] = useState<FeedLayerDraft>(() =>
    layer
      ? feedLayerDraft(layer)
      : {
          feed_id: startFeed?.id ?? '',
          title: '',
          description: '',
          color: startFeed?.color ?? '#2563eb',
          icon: '',
          order: 100,
          class_labels: [],
        },
  );
  const [id, setId] = useState(layer?.id ?? '');
  const [idTouched, setIdTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readOnly = !canEdit || busy || Boolean(layer?.shared_from);
  const feed = feeds.find((f) => f.id === draft.feed_id) ?? null;
  const { types, error: typesError } = useFeedTypes(workspaceId, feed);
  const set = <K extends keyof FeedLayerDraft>(key: K, value: FeedLayerDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  useEffect(() => {
    if (!isNew || idTouched) return;
    setId(slugifyLayerId(`${draft.feed_id}-${draft.title || 'layer'}`));
  }, [isNew, idTouched, draft.feed_id, draft.title]);

  // Selected types first (even if not in the live data), then the rest of the feed.
  const typeRows = useMemo(() => {
    const rows = new Map<string, number | undefined>();
    for (const label of draft.class_labels) rows.set(label, undefined);
    for (const t of types ?? []) rows.set(t.label, t.count);
    return [...rows].map(([label, count]) => ({ label, count }));
  }, [draft.class_labels, types]);

  const toggleType = (label: string, on: boolean) =>
    set(
      'class_labels',
      on ? [...draft.class_labels, label] : draft.class_labels.filter((value) => value !== label),
    );

  const save = async () => {
    const layerId = id.trim();
    if (!draft.title.trim()) return setError('Title is required.');
    if (!draft.feed_id) return setError('Pick a feed.');
    if (isNew && !ID_PATTERN.test(layerId)) {
      return setError('Id must be lowercase letters, digits and dashes (max 48).');
    }
    if (isNew && takenIds.has(layerId)) return setError(`Id “${layerId}” is already used.`);
    setBusy(true);
    setError(null);
    try {
      onSaved(await feedLayersApi.save(workspaceId, layerId, draft));
    } catch (e) {
      setError(errorText(e, 'Could not save the layer'));
    } finally {
      setBusy(false);
    }
  };

  if (isNew && feeds.length === 0) {
    return <SettingsNotice>Create a feed first: a layer draws from a feed.</SettingsNotice>;
  }

  return (
    <div className="maps-new-layer-form space-y-4">
      {error ? (
        <SettingsNotice tone="error">
          <span role="alert" className="whitespace-pre-line">{error}</span>
        </SettingsNotice>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        <label className="maps-new-layer-form__field">
          <span>Title</span>
          <Input value={draft.title} disabled={readOnly} onChange={(e) => set('title', e.target.value)} placeholder="Solar" />
        </label>
        <label className="maps-new-layer-form__field">
          <span>Feed</span>
          <Select
            value={draft.feed_id}
            disabled={readOnly || !isNew}
            onChange={(e) => {
              set('feed_id', e.target.value);
              set('class_labels', []);
            }}
            title={isNew ? undefined : 'A layer stays on its feed'}
          >
            {feeds.map((f) => (
              <option key={f.id} value={f.id}>
                {f.title}
              </option>
            ))}
          </Select>
        </label>
        {isNew ? (
          <label className="maps-new-layer-form__field">
            <span>Id</span>
            <Input
              value={id}
              disabled={readOnly}
              className="font-mono"
              spellCheck={false}
              onChange={(e) => {
                setIdTouched(true);
                setId(e.target.value.trim().toLowerCase());
              }}
            />
            <span className="maps-new-layer-form__hint-block">Used in map links (?layer=…).</span>
          </label>
        ) : null}
        <label className="maps-new-layer-form__field">
          <span>Order</span>
          <Input
            type="number"
            value={draft.order}
            disabled={readOnly}
            onChange={(e) => set('order', Number.parseInt(e.target.value, 10) || 0)}
          />
          <span className="maps-new-layer-form__hint-block">Position under the feed in the sidebar.</span>
        </label>
        <label className="maps-new-layer-form__field md:col-span-2">
          <span>Description</span>
          <Input value={draft.description} disabled={readOnly} onChange={(e) => set('description', e.target.value)} placeholder="Optional" />
        </label>
      </div>

      <div className="maps-new-layer-form__field">
        <span>Feature types</span>
        <span className="maps-new-layer-form__hint-block">
          The feed&apos;s features this layer shows (their <code>classLabel</code>). None ticked: every feature.
        </span>
        {feed && !hasFeatureTypes(feed) ? (
          <p className="text-xs text-muted-foreground">SPARQL feeds have no feature types: this layer shows every pin.</p>
        ) : types === null ? (
          <p className="text-xs text-muted-foreground">
            <Loader2 size={12} className="mr-1 inline animate-spin" />
            Reading the feed…
          </p>
        ) : (
          <>
            {typesError ? <p className="text-xs text-destructive">Could not read the feed: {typesError}</p> : null}
            {typeRows.length === 0 ? (
              <p className="text-xs text-muted-foreground">This feed has no feature types.</p>
            ) : (
              <div className="grid gap-1 sm:grid-cols-2">
                {typeRows.map(({ label, count }) => (
                  <label key={label} className={cn('flex items-center gap-2 text-sm', readOnly && 'opacity-70')}>
                    <Checkbox
                      checked={draft.class_labels.includes(label)}
                      disabled={readOnly}
                      onCheckedChange={(on) => toggleType(label, on === true)}
                      aria-label={label}
                    />
                    <span className="truncate">{label}</span>
                    <span className="text-xs text-muted-foreground">{count ?? '—'}</span>
                  </label>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <div className="maps-new-layer-form__row">
        <label className="maps-new-layer-form__field">
          <span>Color</span>
          <Input
            type="color"
            value={draft.color}
            disabled={readOnly}
            onChange={(e) => set('color', e.target.value)}
            className="maps-new-layer-form__color"
          />
          <span className="maps-new-layer-form__hint-block">Pins and Group by country.</span>
        </label>
      </div>

      <div className="maps-new-layer-form__field">
        <span>Icon</span>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={!draft.icon}
            disabled={readOnly}
            onCheckedChange={(on) => set('icon', on === true ? '' : feed?.icon || 'MapPin')}
          />
          Use the feed&apos;s logo
        </label>
        {draft.icon ? <MapsIconGallery value={draft.icon} onChange={(icon) => set('icon', icon)} /> : null}
      </div>

      {canEdit && !layer?.shared_from ? (
        <div className="flex gap-2">
          <Button onClick={() => void save()} disabled={busy}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : null}
            {isNew ? 'Create layer' : 'Save layer'}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
