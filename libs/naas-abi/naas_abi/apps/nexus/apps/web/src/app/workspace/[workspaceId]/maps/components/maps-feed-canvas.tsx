'use client';

import {useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode} from 'react';
import type {Map as LeafletMap, Marker} from 'leaflet';
import {ExternalLink, Loader2, ArrowLeft, Search, List, X} from 'lucide-react';
import {addMapsPinMarkers, captureMapsCamera, clearMapsMarkers, createMapsLeaflet, destroyMapsLeaflet, fitMapsBounds, restoreMapsCamera, type MapsCamera, type MapsPinMarker} from '../lib/leaflet-map';
import {formatMapsFeedAge, graphObjectHref, normalizeFeedLoad, type MapsFeedMeta, type MapsFeedResult} from '../lib/maps-feed';
import {mapsViewFromBounds, type MapsFeedView} from '../lib/maps-view';
import {MapsCoverageLayer} from './maps-coverage-layer';
import {MapsRecordMedia} from './maps-record-media';
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
  legend?: ReactNode;
  refreshMs?: number;
  inspectable?: boolean;
  workspaceId?: string;
  /** Pass the current map bounds into fetchPins and refetch on pan/zoom. */
  viewportBound?: boolean;
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

export function MapsFeedCanvas({title, loadingLabel, readyMeta, emptyTitle='No data', emptyBody='This feed returned no mappable points right now.', sourceHref, sourceLabel='Source', fetchPins, fitMaxZoom=5, legend, refreshMs, inspectable=false, workspaceId='', viewportBound=false}: MapsFeedCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const [panelOpen, setPanelOpen] = useState(false);
  const mapRef = useRef<LeafletMap|null>(null);
  const leafletRef = useRef<typeof import('leaflet')|null>(null);
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
  const [search,setSearch] = useState('');
  const [country,setCountry] = useState('');
  const activePins = view === 'coverage' ? coveragePins : pins;
  const visiblePins = useMemo(() => activePins.filter(p => (!country || p.country===country) && `${p.label} ${p.country??''} ${p.detail??''} ${p.address??''}`.toLowerCase().includes(search.toLowerCase())),[activePins,country,search]);
  const countries = useMemo(() => Array.from(new Set(activePins.map(p=>p.country).filter((v):v is string=>!!v))).sort(),[activePins]);
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

  function selectPin(pin:MapsPinMarker) {
    rememberView();
    setSelected(pin);
    setPanelOpen(true);
    mapRef.current?.setView([pin.lat,pin.lng],Math.max(mapRef.current.getZoom(),pin.memberIds ? 8 : 14));
  }

  const selectCountry = useCallback((value: string) => {
    setCountry(value);
    setSearch('');
    setSelected(null);
    setPanelOpen(true);
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
    setPanelOpen(true);
  }

  function deselectPin() {
    setSelected(null);
    restoreView();
  }

  function closePanel() {
    setPanelOpen(false);
    setSelected(null);
    restoreView();
    toggleRef.current?.focus();
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
        if (!isRefresh && !viewportBound) fitMapsBounds(map, loaded.pins, {maxZoom: fitMaxZoom});
        setError(null);
        setStatus(loaded.pins.length ? 'ready' : 'empty');
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
      destroyMapsLeaflet(ownedMap, ownedMarkers);
      if (mapRef.current === ownedMap) {
        mapRef.current = null;
        leafletRef.current = null;
      }
    };
    // Callers remount when dataset/workspace changes. Public feed factories are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMs, fitMaxZoom, viewportBound]);

  useEffect(()=>{
    if(!leafletRef.current || !mapRef.current) return;
    clearMapsMarkers(markersRef.current);
    addMapsPinMarkers(leafletRef.current,mapRef.current,visiblePins,markersRef.current,inspectable?selectPin:undefined);
    if (view === 'coverage') {
      markersRef.current.forEach((marker, index) => {
        const text = document.createElement('span');
        text.textContent = visiblePins[index].label;
        marker.bindTooltip(text, {direction: 'top', offset: [0,-6], className: 'maps-coverage-tooltip'});
      });
    }
    if (pendingFocusRef.current) {
      const pin = pendingFocusRef.current;
      mapRef.current.setView([pin.lat,pin.lng],14);
      pendingFocusRef.current = null;
    } else if(inspectable && !viewportBound) fitMapsBounds(mapRef.current,visiblePins,{maxZoom:fitMaxZoom});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[visiblePins,inspectable,fitMaxZoom,viewportBound,view]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) return;
    const onBackground = () => closePanel();
    map.on('click', onBackground);
    return () => { map.off('click', onBackground); };
  }, [selected]);

  const overlayTitle =
    status === 'error'
      ? 'Feed unavailable'
      : viewportBound && !feedMeta?.needsKey
        ? 'No data in this view'
        : emptyTitle;
  const overlayBody = status==='error' ? error : (emptyDetail || emptyBody);

  return <div className="maps-canvas">
    <div className="maps-canvas__toolbar">
      <span className="maps-canvas__toolbar-title">{title}</span>
      {status==='loading' && <span className="maps-status maps-status--row"><Loader2 size={14} className="animate-spin"/>{loadingLabel}</span>}
      {status==='ready' && <span className="maps-canvas__toolbar-meta">{view==='coverage' ? `${visiblePins.length} cities · ${new Set(visiblePins.map(p=>p.country)).size} countries` : `${readyMeta(visiblePins.length)}${visiblePins.length!==pins.length?` of ${pins.length}`:''}${freshness?` · ${freshness}`:''}`}</span>}
      {status==='empty' && <span className="maps-canvas__toolbar-meta">{overlayTitle}{freshness?` · ${freshness}`:''}</span>}
      {status==='error' && <span className="maps-status maps-status--error">{error}</span>}
      {inspectable && coveragePins.length > 0 && <div className="maps-view-switch" role="group" aria-label="Map view">
        <button type="button" aria-pressed={view==='addresses'} onClick={()=>switchView('addresses')}>Addresses</button>
        <button type="button" aria-pressed={view==='coverage'} onClick={()=>switchView('coverage')}>City coverage</button>
      </div>}
      {inspectable && (country || search) && <button type="button" className="maps-coverage-reset" aria-label="Clear map filters" onClick={()=>{setCountry('');setSearch('');deselectPin();}}>Show all{country ? ': '+country : ''}<X size={12}/></button>}
      {inspectable && <button ref={toggleRef} type="button" className="maps-record-toggle" aria-expanded={panelOpen} aria-controls={panelId} onClick={() => panelOpen ? closePanel() : setPanelOpen(true)}><List size={15}/>{view==='coverage'?'Cities':'Locations'}</button>}
    </div>
    <div className={`maps-canvas__workspace${inspectable?' maps-canvas__workspace--inspectable':''}`}>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet"/>
        {(status==='empty'||status==='error') && <div className="maps-empty-overlay"><h3>{overlayTitle}</h3><p>{overlayBody}</p>{sourceHref && <a className="maps-btn" href={sourceHref} target="_blank" rel="noreferrer"><ExternalLink size={12}/>{sourceLabel}</a>}</div>}
        {view==='coverage' && status==='ready' && mapRef.current && leafletRef.current && <MapsCoverageLayer map={mapRef.current} leaflet={leafletRef.current} pins={coveragePins} selectedCountry={country} onSelectCountry={selectCountry}/>}
        {legend && (status==='ready'||status==='empty') ? legend : null}
      </div>
      {inspectable && panelOpen && <aside id={panelId} className="maps-record-panel" aria-label="Map locations and evidence" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); closePanel(); } }}>
        <div className="maps-record-header">
          {selected ? <button className="maps-record-back" onClick={deselectPin}><ArrowLeft size={14}/>{view==='coverage'?'All cities':'All locations'}</button> : <h2>{view==='coverage' ? country || 'Cities' : 'Locations'}</h2>}
          <button type="button" className="maps-record-close" aria-label="Close location panel" onClick={closePanel}><X size={16}/></button>
        </div>
        {selected ? <>
          <MapsRecordMedia pin={selected} />
          <p className="maps-record-precision">{selected.precision}</p>
          <p className="maps-record-detail">{selected.detail}</p>
          {selected.observedAt && <p>Observed: <time>{selected.observedAt}</time></p>}
          {selected.entityUri && selected.graphUri && <a className="maps-btn maps-record-kg" href={graphObjectHref(workspaceId,selected.graphUri,selected.entityUri)}>Open in Knowledge Graph <ExternalLink size={14}/></a>}
          {selected.memberIds && <>
            <h3>Addresses ({selected.memberIds.length})</h3>
            <div className="maps-record-list maps-coverage-addresses">{pins.filter(pin=>selected.memberIds?.includes(pin.id)).map(pin=><button key={pin.id} onClick={()=>showAddress(pin)}><strong>{pin.detail?.split('\n')[0] || pin.label}</strong><span>View address</span></button>)}</div>
            {!selected.memberIds.length && <p>No street address is linked to this city yet.</p>}
          </>}
          <h3>Relationships</h3>
          <dl>{selected.relationships?.map((r,i)=><div key={i}><dt>{r.label}</dt><dd>{r.entityUri && selected.graphUri ? <a href={graphObjectHref(workspaceId,selected.graphUri,r.entityUri)}>{r.value}</a>:r.value}</dd></div>)}</dl>
          <h3>Evidence</h3><ul className="maps-record-sources">{selected.sources?.map(s=><li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.title}<ExternalLink size={12}/></a></li>)}</ul>
        </> : <>
          <label className="maps-record-search"><Search size={15}/><input aria-label="Search locations" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search locations…"/></label>
          <select aria-label="Filter locations by country" value={country} onChange={e=>setCountry(e.target.value)}><option value="">All countries</option>{countries.map(c=><option key={c}>{c}</option>)}</select>
          <p className="maps-record-note">{view==='coverage'?'Select a city to see its addresses and graph evidence.':'Select a location for its address, source and map precision.'}</p>
          <div className="maps-record-list">{visiblePins.map(p=><button key={p.id} onClick={()=>selectPin(p)}><strong>{p.label}</strong><span>{p.memberIds ? `${p.memberIds.length} address${p.memberIds.length===1?'':'es'}` : p.country}</span></button>)}</div>
          {status==='ready' && !visiblePins.length && <p>No locations match these filters.</p>}
        </>}
      </aside>}
    </div>
  </div>;
}
