'use client';

import {useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode} from 'react';
import type {Map as LeafletMap, Marker} from 'leaflet';
import {ExternalLink, Loader2, ArrowLeft, X} from 'lucide-react';
import { useMapsStore } from '@/stores/maps';
import {
  basemapLabel,
  installMapsBasemap,
  normalizeBasemapId,
  type MapsBasemapDef,
  type MapsBasemapHandle,
} from '../lib/maps-basemaps';
import { formatMapsToolbarViewLine } from '../lib/maps-toolbar-view';
import { MapsBasemapControl } from './maps-basemap-control';
import { useWorkspaceBasemaps } from '../lib/use-workspace-basemaps';
import { MapsCountryClusterControl } from './maps-country-cluster-control';
import { useCountryCenters } from '../lib/use-country-centers';
import { MapsLocateControl } from './maps-locate-control';
import {
  clusterPinsByCountry,
  COUNTRY_CLUSTER_EXPAND_ZOOM,
  resolveClusterMemberPins,
  DEFAULT_MAPS_GROUP_AREA,
  groupAreaAt,
} from '../lib/maps-country-cluster';
import {addMapsPinMarkers, captureMapsCamera, clearMapsMarkers, createMapsLeaflet, destroyMapsLeaflet, fitMapsBounds, MAPS_DEFAULT_CAMERA, restoreMapsCamera, type MapsCamera, type MapsPinMarker} from '../lib/leaflet-map';
import {formatMapsFeedAge, graphObjectHref, normalizeFeedLoad, type MapsFeedMeta, type MapsFeedResult} from '../lib/maps-feed';
import {mapsViewFromBounds, type MapsFeedView} from '../lib/maps-view';
import {MapsCoverageLayer} from './maps-coverage-layer';
import {MapsPointSearch} from './maps-point-search';
import {pinSearchHaystack} from '../lib/maps-pin-search';
import {
  MapsCountryFilterControl,
  isCountryFilterActive,
  mapsCountryFilterAll,
  pinMatchesCountryFilter,
  type MapsCountryFilter,
} from './maps-country-filter-control';
import {
  MapsRegionFilterControl,
  isRegionFilterActive,
  mapsRegionFilterAll,
  type MapsRegionFilter,
} from './maps-region-filter-control';
import {
  continentsOnPins,
  pinMatchesRegionFilter,
} from '../lib/maps-pin-region';
import {MapsRecordMedia} from './maps-record-media';
import { MapsActiveLayersLegend, type LayerLegendStatus } from './maps-active-layers-legend';
import { aggregateLayerLegendSublayers } from '../lib/maps-layer-legend-utils';
import { layerPinColor } from '../lib/maps-layer-colors';
import { useMapLayers } from '../lib/use-map-layouts';
import { useMapsLayerParams } from '../lib/use-maps-layer-params';
import { MapsRegionLabels } from './maps-region-labels';
import {
  distinctMapFeedIds,
  facilityCountsByRegionAndFeed,
  pinCountriesInMapRegion,
  basemapRegionOverlay,
  showMapRegionLabelsAtZoom,
} from '../lib/maps-map-regions';
import './maps-components.css';

export type MapsFeedStatus = 'loading' | 'ready' | 'error' | 'empty';
export type MapsFeedLoad = MapsPinMarker[] | MapsFeedResult;

export interface MapsFeedCanvasProps {
  title: string;
  loadingLabel: string;
  readyMeta: (count: number) => string;
  emptyTitle?: string;
  emptyBody?: string;
  sourceHref?: string;
  sourceLabel?: string;
  fetchPins: (signal: AbortSignal, view?: MapsFeedView) => Promise<MapsFeedLoad>;
  fitMaxZoom?: number;
  /** Pin / symbology rows (expand under this feed’s layer row in the legend). */
  legend?: ReactNode;
  /** Layer ids shown in the active-layers legend (defaults to store overrides). */
  legendLayerIds?: string[];
  /** Counts for sidebar layers switched on (Active layers map). */
  legendStatuses?: Record<string, LayerLegendStatus>;
  /** Symbology for multiple layers (Active layers map). Merged with `legend` + `legendLayerId`. */
  feedLegendsByLayerId?: Record<string, ReactNode>;
  /** This feed’s dataset id — updates that row’s count on single-layer maps. */
  legendLayerId?: string;
  refreshMs?: number;
  inspectable?: boolean;
  workspaceId?: string;
  /** Pass the current map bounds into fetchPins and refetch on pan/zoom. */
  viewportBound?: boolean;
  /** Background under the pins. Defaults to the member's choice, then the catalog default. */
  basemapId?: string;
  /** Full basemap catalog; defaults to the workspace catalog. */
  basemapDefs?: readonly MapsBasemapDef[];
  /** Subset for the map type picker; defaults to the workspace's shown basemaps. */
  basemapPickerDefs?: readonly MapsBasemapDef[];
  /** When false, empty feeds only update the toolbar (map stays visible). */
  emptyOverlay?: boolean;
  /** Top-left search over loaded pins (submit on Enter). */
  pointSearch?: boolean;
  layerTitleForPin?: (pin: MapsPinMarker) => string | undefined;
  /** Extra layers after basemap (e.g. FIRMS WMS). Return cleanup on unmount. */
  onMapReady?: (ctx: {
    L: typeof import('leaflet');
    map: LeafletMap;
  }) => void | (() => void);
}

function viewFromMap(map: LeafletMap): MapsFeedView {
  const bounds = map.getBounds();
  const center = map.getCenter();
  return mapsViewFromBounds({
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
    lat: center.lat,
    lng: center.lng,
    zoom: map.getZoom(),
  });
}

function metaLine(meta: MapsFeedMeta | null, now: number): string {
  if (!meta) return '';
  const parts: string[] = [];
  if (meta.attribution || meta.source) parts.push(meta.attribution || meta.source || '');
  if (meta.coverage) parts.push(meta.coverage);
  if (meta.observedAt) {
    const age = formatMapsFeedAge(meta.observedAt, now);
    if (age) parts.push(age);
  }
  if (meta.stale) parts.push('stale');
  return parts.filter(Boolean).join(' · ');
}

export function MapsFeedCanvas({title, loadingLabel, readyMeta, emptyTitle='No data', emptyBody='This feed returned no mappable points right now.', sourceHref, sourceLabel='Source', fetchPins, fitMaxZoom=5, legend, legendLayerIds, legendStatuses, feedLegendsByLayerId, legendLayerId, refreshMs, inspectable=false, workspaceId='', viewportBound=false, basemapId, basemapDefs: basemapDefsProp, basemapPickerDefs, emptyOverlay=true, pointSearch=true, layerTitleForPin, onMapReady}: MapsFeedCanvasProps) {
  const mapLayers = useMapLayers();
  const workspaceBasemaps = useWorkspaceBasemaps(workspaceId || mapLayers.workspaceId);
  const basemapDefs = basemapDefsProp ?? workspaceBasemaps.allDefs;
  const pickerDefsBase = basemapPickerDefs ?? workspaceBasemaps.defs;
  const { layerIds: urlLayerIds } = useMapsLayerParams();
  const groupBy = useMapsStore((s) => s.groupBy);
  const setGroupBy = useMapsStore((s) => s.setGroupBy);
  const grouping = groupBy !== 'off';
  const countryCenters = useCountryCenters(grouping || inspectable);
  const legendWorkspaceId = workspaceId || mapLayers.workspaceId;
  const legendEntries = useMemo(() => {
    if (legendLayerIds) {
      const active = new Set(legendLayerIds);
      return mapLayers.entries.filter((entry) => active.has(entry.id));
    }
    // Same layers as the map: the URL's choice.
    const on = new Set(urlLayerIds);
    return mapLayers.entries.filter((entry) => entry.combinable && on.has(entry.id));
  }, [legendLayerIds, mapLayers.entries, urlLayerIds]);
  const legendLayerColor = useMemo(() => {
    if (!legendLayerId) return undefined;
    const entry = mapLayers.entries.find((e) => e.id === legendLayerId);
    return entry ? layerPinColor(entry) : undefined;
  }, [legendLayerId, mapLayers.entries]);
  const [feedLegendStatuses, setFeedLegendStatuses] = useState<Record<string, LayerLegendStatus>>({});
  const mergedLegendStatuses = useMemo(
    () => ({ ...feedLegendStatuses, ...legendStatuses }),
    [feedLegendStatuses, legendStatuses],
  );
  const mergedFeedLegends = useMemo(() => {
    const merged = { ...feedLegendsByLayerId };
    if (legendLayerId && legend) merged[legendLayerId] = legend;
    return Object.keys(merged).length ? merged : undefined;
  }, [feedLegendsByLayerId, legendLayerId, legend]);
  const storedBasemap = useMapsStore((s) => s.basemapId);
  const setBasemap = useMapsStore((s) => s.setBasemap);
  const basemap = normalizeBasemapId(
    basemapId ?? storedBasemap,
    basemapDefs,
    workspaceBasemaps.defaultBasemapId,
  );
  const pickerDefs = useMemo(() => {
    if (pickerDefsBase.some((def) => def.id === basemap)) return pickerDefsBase;
    // A layer's default basemap may be hidden from the picker: still show what is drawn.
    const drawn = basemapDefs.find((def) => def.id === basemap);
    return drawn ? [...pickerDefsBase, drawn] : pickerDefsBase;
  }, [pickerDefsBase, basemap, basemapDefs]);
  const containerRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const [panelOpen, setPanelOpen] = useState(false);
  const [countryPickerOpen, setCountryPickerOpen] = useState(false);
  const [regionPickerOpen, setRegionPickerOpen] = useState(false);
  const mapRef = useRef<LeafletMap|null>(null);
  const leafletRef = useRef<typeof import('leaflet')|null>(null);
  const preserveUserViewRef = useRef(false);
  // Pins the view was last fitted to: re-fit on new data, not when the same
  // pins are re-drawn (e.g. group-by-country switching at the zoom threshold).
  const fittedPinsRef = useRef<MapsPinMarker[] | null>(null);
  const onMapReadyRef = useRef(onMapReady);
  onMapReadyRef.current = onMapReady;
  const mapReadyExtraCleanupRef = useRef<(() => void) | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [camera, setCamera] = useState<MapsCamera | null>(null);
  const [viewRadiusNm, setViewRadiusNm] = useState<number | null>(null);
  const basemapHandleRef = useRef<MapsBasemapHandle | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [status,setStatus] = useState<MapsFeedStatus>('loading');
  const [error,setError] = useState<string|null>(null);
  const [pins,setPins] = useState<MapsPinMarker[]>([]);
  const [coveragePins,setCoveragePins] = useState<MapsPinMarker[]>([]);
  const [view,setView] = useState<'addresses'|'coverage'>('addresses');
  const pendingFocusRef = useRef<MapsPinMarker|null>(null);
  const returnViewRef = useRef<MapsCamera|null>(null);
  const [feedMeta,setFeedMeta] = useState<MapsFeedMeta|null>(null);
  const [emptyDetail,setEmptyDetail] = useState<string|null>(null);
  const [selected,setSelected] = useState<MapsPinMarker|null>(null);
  // Country / continent marker whose locations the panel lists.
  const [group,setGroup] = useState<MapsPinMarker|null>(null);
  // Bumped whenever the panel under search opens, which closes search results.
  const [panelKey,setPanelKey] = useState(0);
  const [search,setSearch] = useState('');
  const [countryFilter,setCountryFilter] = useState<MapsCountryFilter>(mapsCountryFilterAll);
  const [regionFilter, setRegionFilter] = useState<MapsRegionFilter>(mapsRegionFilterAll);
  const [coverageCountry,setCoverageCountry] = useState('');
  const activePins = view === 'coverage' ? coveragePins : pins;
  const pointSearchPins = activePins;
  const locationsListMode = panelOpen && !selected && !group;
  const visiblePins = useMemo(() => {
    const q = search.trim().toLowerCase();
    const applyText = locationsListMode;
    return activePins.filter((p) => {
      if (!pinMatchesCountryFilter(p.country, countryFilter)) return false;
      if (!pinMatchesRegionFilter(p, regionFilter, countryCenters)) return false;
      if (applyText && q && !pinSearchHaystack(p).includes(q)) return false;
      return true;
    });
  }, [activePins, countryFilter, regionFilter, countryCenters, search, locationsListMode]);
  const canCountryCluster = useMemo(
    () => visiblePins.some((p) => p.country?.trim()),
    [visiblePins],
  );
  const mapZoom = camera?.zoom ?? MAPS_DEFAULT_CAMERA.zoom;
  const displayPins = useMemo(() => {
    const area = groupAreaAt(groupBy, DEFAULT_MAPS_GROUP_AREA, mapZoom, view);
    if (!area || groupBy === 'off') return visiblePins;
    return clusterPinsByCountry(visiblePins, {
      layerTitle: layerTitleForPin,
      groupBy,
      centers: countryCenters,
      area,
    });
    // layerTitleForPin is a render-time callback; titles only label the badges.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visiblePins, groupBy, countryCenters, mapZoom, view]);
  const groupMembers = useMemo(() => {
    if (!group) return [];
    const members = resolveClusterMemberPins(group, visiblePins);
    if (groupBy !== 'feed') return members;
    // Feed grouping counts a site once even when it sits in several layers.
    const seen = new Set<string>();
    return members.filter((pin) => {
      const site = `${pin.feedId ?? pin.layerId ?? ''}:${pin.featureId ?? pin.id}`;
      if (seen.has(site)) return false;
      seen.add(site);
      return true;
    });
  }, [group, visiblePins, groupBy]);
  const countries = useMemo(() => Array.from(new Set(activePins.map(p=>p.country).filter((v):v is string=>!!v))).sort(),[activePins]);
  const continents = useMemo(
    () => continentsOnPins(activePins, countryCenters),
    [activePins, countryCenters],
  );
  const canRegionFilter = continents.length > 0;
  // Regions belong to the basemap drawn (its renderer), not to the layers on it.
  const activeRegionOverlay = useMemo(() => {
    if (view !== 'addresses') return null;
    return basemapRegionOverlay(basemapDefs.find((def) => def.id === basemap)?.renderer) ?? null;
  }, [basemapDefs, basemap, view]);
  const regionFacilityCountsByFeed = useMemo(() => {
    if (!activeRegionOverlay) return new Map();
    return facilityCountsByRegionAndFeed(
      pins,
      activeRegionOverlay.countryToRegion,
      countryCenters,
    );
  }, [activeRegionOverlay, pins, countryCenters]);
  const regionLabelsMultiFeed = useMemo(
    () => distinctMapFeedIds(pins) > 1,
    [pins],
  );
  const selectMapRegion = useCallback(
    (regionId: string) => {
      if (!activeRegionOverlay) return;
      const inRegion = pinCountriesInMapRegion(
        regionId,
        pins,
        activeRegionOverlay.countryToRegion,
        countryCenters,
      );
      setCountryFilter(
        inRegion.length === 0
          ? mapsCountryFilterAll()
          : { mode: 'some', countries: new Set(inRegion) },
      );
      setSearch('');
      setSelected(null);
      setGroup(null);
    },
    [activeRegionOverlay, pins, countryCenters],
  );
  const freshness = metaLine(feedMeta, Date.now());

  function rememberView() {
    const map = mapRef.current;
    if (!map || returnViewRef.current) return;
    returnViewRef.current = captureMapsCamera(map);
  }

  function restoreView() {
    const map = mapRef.current;
    const saved = returnViewRef.current;
    returnViewRef.current = null;
    if (!map) return;
    if (saved) {
      restoreMapsCamera(map, saved);
      return;
    }
    if (!viewportBound) fitMapsBounds(map, visiblePins, {maxZoom: fitMaxZoom});
  }

  function openPanel() {
    setPanelOpen(true);
    setPanelKey((key) => key + 1);
  }

  function selectPin(pin:MapsPinMarker) {
    rememberView();
    setSelected(pin);
    openPanel();
    mapRef.current?.setView([pin.lat,pin.lng],Math.max(mapRef.current.getZoom(),pin.memberIds ? 8 : 14));
  }

  const handleMapPinSelect = useCallback(
    (pin: MapsPinMarker) => {
      const map = mapRef.current;
      // Country marker (any size): zoom in on its sites and list them under search.
      if (pin.clusterCount && pin.memberIds?.length && map) {
        rememberView();
        preserveUserViewRef.current = true;
        const members = resolveClusterMemberPins(pin, visiblePins);
        fitMapsBounds(map, members, {
          maxZoom: Math.max(COUNTRY_CLUSTER_EXPAND_ZOOM, map.getZoom() + 1),
        });
        if (pin.country) setCountryFilter(mapsCountryFilterAll());
        setSelected(null);
        setGroup(pin);
        openPanel();
        return;
      }
      selectPin(pin);
    },
    // selectPin / openPanel only use setters and refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visiblePins],
  );

  const focusMapPin = useCallback((pin: MapsPinMarker) => {
    setGroup(null);
    selectPin(pin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectCountry = useCallback((value: string) => {
    setCountryFilter({ mode: 'some', countries: new Set([value]) });
    setCoverageCountry(value);
    setSearch('');
    setSelected(null);
    setGroup(null);
    openPanel();
    const map = mapRef.current;
    const saved = returnViewRef.current;
    returnViewRef.current = null;
    if (map && saved) restoreMapsCamera(map, saved);
  }, []);

  function switchView(value: 'addresses'|'coverage') {
    setView(value);
    setSelected(null);
    pendingFocusRef.current = null;
    restoreView();
  }

  function showAddress(pin: MapsPinMarker) {
    rememberView();
    pendingFocusRef.current = pin;
    setView('addresses');
    setSearch('');
    setSelected(pin);
    openPanel();
  }

  /** Back from a location: to its group when it came from one, else to the list. */
  function deselectPin() {
    setSelected(null);
    if (!group) restoreView();
  }

  function closePanel() {
    setPanelOpen(false);
    setCountryPickerOpen(false);
    setSelected(null);
    setGroup(null);
    restoreView();
  }

  function openLocationsList() {
    setSelected(null);
    setGroup(null);
    openPanel();
  }

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    let moveTimer: ReturnType<typeof setTimeout> | null = null;
    let active: AbortController | null = null;
    let ownedMap: LeafletMap | null = null;
    const ownedMarkers: Marker[] = [];
    const lifecycle = new AbortController();
    markersRef.current = ownedMarkers;

    // One initialization per effect, shared even if a refresh starts while
    // Leaflet is loading. Cleanup cancels it before it can claim the container.
    const mapReady = createMapsLeaflet(container, {}, lifecycle.signal).then(({L, map}) => {
      if (cancelled) {
        map.remove();
        return null;
      }
      ownedMap = map;
      mapRef.current = map;
      leafletRef.current = L;
      basemapHandleRef.current = installMapsBasemap(L, map, basemap, undefined, {
        defs: basemapDefs,
      });
      mapReadyExtraCleanupRef.current?.();
      const extra = onMapReadyRef.current?.({ L, map });
      mapReadyExtraCleanupRef.current = typeof extra === 'function' ? extra : null;
      setMapReady(true);
      setCamera(captureMapsCamera(map));
      return map;
    }).catch((err) => {
      if (cancelled || lifecycle.signal.aborted) return null;
      throw err;
    });

    async function loadPins(isRefresh: boolean) {
      if (cancelled) return;
      if (!isRefresh) {
        setStatus('loading');
        setError(null);
      }
      active?.abort();
      const controller = new AbortController();
      active = controller;
      const timeout = setTimeout(() => controller.abort(new Error('Map feed request timed out.')), 25000);
      try {
        const map = await mapReady;
        if (!map || cancelled || active !== controller) return;
        controller.signal.throwIfAborted();
        const mapView = viewportBound ? viewFromMap(map) : undefined;
        const loaded = normalizeFeedLoad(await fetchPins(controller.signal, mapView));
        if (cancelled || active !== controller) return;
        controller.signal.throwIfAborted();
        const cities = loaded.coveragePins ?? [];
        // A rebuilt map must redraw even when a static feed reuses its array.
        setPins([...loaded.pins]);
        setCoveragePins([...cities]);
        if (!cities.length) setView('addresses');
        setFeedMeta({
          source: loaded.source,
          attribution: loaded.attribution,
          observedAt: loaded.observedAt,
          stale: loaded.stale,
          needsKey: loaded.needsKey,
          status: loaded.status,
          coverage: loaded.coverage,
        });
        setEmptyDetail(loaded.reason ?? null);
        setSelected(current => current ? [...loaded.pins,...cities].find(p => p.id === current.id) ?? null : null);
        if (!isRefresh && !viewportBound && !preserveUserViewRef.current) {
          fitMapsBounds(map, loaded.pins, {maxZoom: fitMaxZoom});
        }
        setError(null);
        setStatus(loaded.pins.length ? 'ready' : 'empty');
        if (legendLayerId) {
          setFeedLegendStatuses({
            [legendLayerId]: {
              count: loaded.pins.length,
              sublayers: aggregateLayerLegendSublayers(loaded.pins, legendLayerColor),
            },
          });
        }
      } catch (err) {
        if (cancelled || active !== controller) return;
        setPins([]);
        setCoveragePins([]);
        setView('addresses');
        setSelected(null);
        setFeedMeta(null);
        setEmptyDetail(null);
        setError(err instanceof Error ? err.message : 'Failed to load feed');
        setStatus('error');
        if (legendLayerId) {
          setFeedLegendStatuses({
            [legendLayerId]: {
              error: err instanceof Error ? err.message : 'Failed to load feed',
            },
          });
        }
      } finally {
        clearTimeout(timeout);
      }
    }

    void loadPins(false);
    if (refreshMs && refreshMs > 0) timer = setInterval(() => { void loadPins(true); }, refreshMs);

    void mapReady.then((map) => {
      if (!map || cancelled || !viewportBound) return;
      const onMove = () => {
        if (moveTimer) clearTimeout(moveTimer);
        moveTimer = setTimeout(() => { void loadPins(true); }, 500);
      };
      map.on('moveend', onMove);
    }).catch(() => {});

    return () => {
      cancelled = true;
      lifecycle.abort();
      try { active?.abort(); } catch { /* ignore */ }
      if (timer) clearInterval(timer);
      if (moveTimer) clearTimeout(moveTimer);
      mapReadyExtraCleanupRef.current?.();
      mapReadyExtraCleanupRef.current = null;
      basemapHandleRef.current?.cleanup();
      basemapHandleRef.current = null;
      destroyMapsLeaflet(ownedMap, ownedMarkers);
      if (mapRef.current === ownedMap) {
        mapRef.current = null;
        leafletRef.current = null;
      }
      setMapReady(false);
    };
    // Callers remount when dataset/workspace changes. Public feed factories are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMs, fitMaxZoom, viewportBound]);

  useEffect(() => {
    basemapHandleRef.current?.setBasemap(basemap, basemapDefs);
  }, [basemap, basemapDefs]);

  useEffect(()=>{
    if(!leafletRef.current || !mapRef.current) return;
    clearMapsMarkers(markersRef.current);
    addMapsPinMarkers(
      leafletRef.current,
      mapRef.current,
      displayPins,
      markersRef.current,
      handleMapPinSelect,
    );
    if (view === 'coverage') {
      markersRef.current.forEach((marker, index) => {
        const text = document.createElement('span');
        text.textContent = displayPins[index].label;
        marker.bindTooltip(text, {direction: 'top', offset: [0,-6], className: 'maps-coverage-tooltip'});
      });
    }
    if (pendingFocusRef.current) {
      const pin = pendingFocusRef.current;
      mapRef.current.setView([pin.lat,pin.lng],14);
      pendingFocusRef.current = null;
    } else if (
      inspectable
      && !viewportBound
      && !preserveUserViewRef.current
      && fittedPinsRef.current !== visiblePins
    ) {
      fitMapsBounds(mapRef.current, displayPins, {maxZoom: fitMaxZoom});
    }
    fittedPinsRef.current = visiblePins;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[displayPins,inspectable,fitMaxZoom,viewportBound,view,handleMapPinSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const clearPreserve = () => {
      preserveUserViewRef.current = false;
    };
    map.on('dragstart', clearPreserve);
    return () => {
      map.off('dragstart', clearPreserve);
    };
  }, [mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      setCamera(null);
      setViewRadiusNm(null);
      return;
    }
    const syncView = () => {
      setCamera(captureMapsCamera(map));
      if (viewportBound) {
        setViewRadiusNm(viewFromMap(map).radiusNm);
      } else {
        setViewRadiusNm(null);
      }
    };
    syncView();
    map.on('moveend', syncView);
    map.on('zoomend', syncView);
    return () => {
      map.off('moveend', syncView);
      map.off('zoomend', syncView);
    };
  }, [mapReady, viewportBound]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || (!selected && !group)) return;
    const onBackground = () => closePanel();
    map.on('click', onBackground);
    return () => { map.off('click', onBackground); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, group]);

  const overlayTitle =
    status === 'error'
      ? 'Feed unavailable'
      : viewportBound && !feedMeta?.needsKey
        ? 'No data in this view'
        : emptyTitle;
  const overlayBody = status==='error' ? error : (emptyDetail || emptyBody);

  const feedMetaLine =
    status === 'ready'
      ? view === 'coverage'
        ? `${visiblePins.length} cities · ${new Set(visiblePins.map((p) => p.country)).size} countries`
        : `${readyMeta(visiblePins.length)}${visiblePins.length !== pins.length ? ` of ${pins.length}` : ''}${freshness ? ` · ${freshness}` : ''}`
      : status === 'empty'
        ? `${overlayTitle}${freshness ? ` · ${freshness}` : ''}`
        : null;

  const viewMetaLine =
    status !== 'error'
      ? formatMapsToolbarViewLine({
          zoom: camera?.zoom ?? MAPS_DEFAULT_CAMERA.zoom,
          lat: camera?.lat ?? MAPS_DEFAULT_CAMERA.lat,
          lng: camera?.lng ?? MAPS_DEFAULT_CAMERA.lng,
          basemapLabel: basemapLabel(basemap, basemapDefs),
          radiusNm: viewRadiusNm ?? undefined,
        })
      : null;

  const recordListOnly = !selected && !group && view !== 'coverage';
  const recordPanel = <section id={panelId} className={`maps-record-panel${recordListOnly ? ' maps-record-panel--list' : ''}`} aria-label="Map locations and evidence" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); closePanel(); } }}>
    {!recordListOnly ? (
      <div className="maps-record-header">
        {selected ? (
          group || inspectable
            ? <button className="maps-record-back" onClick={deselectPin}><ArrowLeft size={14}/>{group ? group.label : view==='coverage'?'All cities':'All locations'}</button>
            : <span/>
        ) : group ? (
          <h2>{group.label}</h2>
        ) : (
          <h2>{coverageCountry || 'Cities'}</h2>
        )}
        <button type="button" className="maps-record-close" aria-label="Close location panel" onClick={closePanel}><X size={16}/></button>
      </div>
    ) : null}
    {selected ? <>
      <MapsRecordMedia pin={selected} />
      {selected.precision && <p className="maps-record-precision">{selected.precision}</p>}
      {selected.detail && <p className="maps-record-detail">{selected.detail}</p>}
      {selected.observedAt && <p>Observed: <time>{selected.observedAt}</time></p>}
      {selected.entityUri && selected.graphUri && <a className="maps-btn maps-record-kg" href={graphObjectHref(workspaceId,selected.graphUri,selected.entityUri)}>Open in Knowledge Graph <ExternalLink size={14}/></a>}
      {selected.memberIds && <>
        <h3>Addresses ({selected.memberIds.length})</h3>
        <div className="maps-record-list maps-coverage-addresses">{pins.filter(pin=>selected.memberIds?.includes(pin.id)).map(pin=><button key={pin.id} onClick={()=>showAddress(pin)}><strong>{pin.detail?.split('\n')[0] || pin.label}</strong><span>View address</span></button>)}</div>
        {!selected.memberIds.length && <p>No street address is linked to this city yet.</p>}
      </>}
      {selected.relationships?.length ? <>
        <h3>Relationships</h3>
        <dl>{selected.relationships.map((r,i)=><div key={i}><dt>{r.label}</dt><dd>{r.entityUri && selected.graphUri ? <a href={graphObjectHref(workspaceId,selected.graphUri,r.entityUri)}>{r.value}</a>:r.value}</dd></div>)}</dl>
      </> : null}
      {selected.sources?.length ? <>
        <h3>Evidence</h3><ul className="maps-record-sources">{selected.sources.map(s=><li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}<ExternalLink size={12}/></a></li>)}</ul>
      </> : null}
    </> : group ? <>
      <div className="maps-record-group">
        {(group.clusterLayers ?? []).map(layer => <span key={layer.layerId} className="maps-record-group__badge"><span className="maps-record-group__swatch" style={{background: layer.color}} aria-hidden/>{layer.title ?? 'Locations'}<strong>{layer.count}</strong></span>)}
      </div>
      <div className="maps-record-list">{groupMembers.map(p=><button key={p.id} onClick={()=>selectPin(p)}><strong>{p.label}</strong><span>{(groupBy === 'feed' ? p.feedTitle : undefined) ?? layerTitleForPin?.(p) ?? p.country}</span></button>)}</div>
      {!groupMembers.length && <p>No locations in this group.</p>}
    </> : <>
      <div className="maps-record-list">{visiblePins.map(p=><button key={p.id} onClick={()=>selectPin(p)}><strong>{p.label}</strong><span>{p.memberIds ? `${p.memberIds.length} address${p.memberIds.length===1?'':'es'}` : p.country}</span></button>)}</div>
      {status==='ready' && !visiblePins.length && <p>No locations match these filters.</p>}
    </>}
  </section>;

  return <div className="maps-canvas">
    <div className="maps-canvas__toolbar">
      <span className="maps-canvas__toolbar-title">{title}</span>
      {status==='loading' && <span className="maps-status maps-status--row"><Loader2 size={14} className="animate-spin"/>{loadingLabel}</span>}
      {feedMetaLine ? <span className="maps-canvas__toolbar-meta">{feedMetaLine}</span> : null}
      {viewMetaLine ? <span className="maps-canvas__toolbar-view">{viewMetaLine}</span> : null}
      {status==='error' && <span className="maps-status maps-status--error">{error}</span>}
      {inspectable && coveragePins.length > 0 && <div className="maps-view-switch" role="group" aria-label="Map view">
        <button type="button" aria-pressed={view==='addresses'} onClick={()=>switchView('addresses')}>Addresses</button>
        <button type="button" aria-pressed={view==='coverage'} onClick={()=>switchView('coverage')}>City coverage</button>
      </div>}
      {inspectable && (isCountryFilterActive(countryFilter) || isRegionFilterActive(regionFilter) || search) && <button type="button" className="maps-coverage-reset" aria-label="Clear map filters" onClick={()=>{setCountryFilter(mapsCountryFilterAll());setRegionFilter(mapsRegionFilterAll());setCoverageCountry('');setSearch('');deselectPin();}}>Show all<X size={12}/></button>}
      <div className="maps-canvas__toolbar-actions">
        <MapsCountryClusterControl
          groupBy={groupBy}
          onGroupByChange={setGroupBy}
          visible={canCountryCluster && view === 'addresses'}
        />
      </div>
    </div>
    <div className={`maps-canvas__workspace${inspectable?' maps-canvas__workspace--inspectable':''}`}>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet"/>
        {(status==='error' || (status==='empty' && emptyOverlay)) ? (
          <div className="maps-empty-overlay" aria-live="polite">
            <h3>{overlayTitle}</h3>
            <p>{overlayBody}</p>
            {sourceHref ? (
              <a className="maps-btn" href={sourceHref} target="_blank" rel="noreferrer">
                <ExternalLink size={12} />
                {sourceLabel}
              </a>
            ) : null}
          </div>
        ) : null}
        {view==='coverage' && status==='ready' && mapRef.current && leafletRef.current && <MapsCoverageLayer map={mapRef.current} leaflet={leafletRef.current} pins={coveragePins} selectedCountry={coverageCountry} onSelectCountry={selectCountry}/>}
        {activeRegionOverlay
        && showMapRegionLabelsAtZoom(mapZoom)
        && (status === 'ready' || status === 'empty') ? (
          <MapsRegionLabels
            regions={activeRegionOverlay.regions}
            countsByFeed={regionFacilityCountsByFeed}
            multiFeed={regionLabelsMultiFeed}
            onSelectRegion={selectMapRegion}
          />
        ) : null}
        {status === 'ready' || status === 'empty' || panelOpen ? (
          <MapsPointSearch
            pins={pointSearchPins}
            searchable={pointSearch && pointSearchPins.length > 0}
            layerTitleForPin={layerTitleForPin}
            onSelectPin={focusMapPin}
            resetKey={panelKey}
            recordPanelMode={inspectable}
            query={search}
            onQueryChange={inspectable ? setSearch : undefined}
            liveEdit={inspectable && locationsListMode}
            placeholder="Search locations…"
            onSearchSubmit={() => {
              setSelected(null);
              setGroup(null);
              openLocationsList();
            }}
            onResultsOpen={() => {
              setPanelOpen(false);
              setSelected(null);
              setGroup(null);
            }}
            actions={inspectable ? (
              <span className="maps-point-search__filters">
                {canRegionFilter ? (
                  <MapsRegionFilterControl
                    regions={continents}
                    selected={regionFilter}
                    onChange={setRegionFilter}
                    open={regionPickerOpen}
                    onOpenChange={(open) => {
                      setRegionPickerOpen(open);
                      if (open) setCountryPickerOpen(false);
                    }}
                  />
                ) : null}
                <MapsCountryFilterControl
                  countries={countries}
                  selected={countryFilter}
                  onChange={setCountryFilter}
                  open={countryPickerOpen}
                  onOpenChange={(open) => {
                    setCountryPickerOpen(open);
                    if (open) setRegionPickerOpen(false);
                  }}
                />
              </span>
            ) : null}
          >
            {panelOpen ? recordPanel : null}
          </MapsPointSearch>
        ) : null}
        <MapsBasemapControl
          basemapId={basemap}
          basemapDefs={pickerDefs}
          workspaceId={workspaceId || mapLayers.workspaceId || ''}
          onBasemapChange={setBasemap}
        />
        <MapsLocateControl
          mapRef={mapRef}
          leafletRef={leafletRef}
          mapReady={mapReady}
          onLocated={() => {
            preserveUserViewRef.current = true;
          }}
        />
        <div className="maps-legend-panel">
          <MapsActiveLayersLegend
            workspaceId={legendWorkspaceId}
            entries={legendEntries}
            statuses={mergedLegendStatuses}
            noLayers={legendEntries.length === 0}
            feedLegendsByLayerId={mergedFeedLegends}
          />
        </div>
      </div>
    </div>
  </div>;
}
