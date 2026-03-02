'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import * as satelliteJs from 'satellite.js';
import type { ShaderMode, LayerId, DetectionMode, TrackedEntity, ShaderParams, SatelliteRecord, CCTVCamera } from '@/lib/types';
import { CRT_SHADER, THERMAL_SHADER, FLARE_SHADER } from '@/lib/shaders';
import { CITIES, CITY_KEYS } from '@/data/landmarks';
import StatusBar from './ui/StatusBar';
import ShaderPanel from './ui/ShaderPanel';
import DataLayerPanel from './ui/DataLayerPanel';
import TrackingOverlay from './ui/TrackingOverlay';
import CCTVPanel from './ui/CCTVPanel';
import { type GeoResult } from './ui/GeoSearch';
import IntelPanel from './ui/IntelPanel';
import IntelTicker from './ui/IntelTicker';
// ─── Globe Engine (hexagonal architecture) ───────────────────────────────────
import { createGlobeEngine, type GlobeEngine } from '@/lib/globe/GlobeEngine';
import { BorderLayerAdapter } from '@/lib/globe/adapters/layers/BorderLayerAdapter';
import { CityLabelAdapter } from '@/lib/globe/adapters/layers/CityLabelAdapter';
import { ConflictZoneAdapter } from '@/lib/globe/adapters/layers/ConflictZoneAdapter';
import { CCTVLayerAdapter } from '@/lib/globe/adapters/layers/CCTVLayerAdapter';
import { FlightLayerAdapter } from '@/lib/globe/adapters/layers/FlightLayerAdapter';
import { MilitaryLayerAdapter } from '@/lib/globe/adapters/layers/MilitaryLayerAdapter';
import { TheaterAircraftAdapter } from '@/lib/globe/adapters/layers/TheaterAircraftAdapter';
import { EarthquakeLayerAdapter } from '@/lib/globe/adapters/layers/EarthquakeLayerAdapter';
import {
  FlightDataSource, MilitaryDataSource, TheaterAircraftDataSource,
} from '@/lib/globe/adapters/data/FlightDataSource';
import {
  EarthquakeDataSource, CCTVDataSource, ConflictEventDataSource,
} from '@/lib/globe/adapters/data/SpatialDataSources';

// --- State defaults ---
const DEFAULT_SHADER_PARAMS: ShaderParams = {
  scanlineIntensity: 0.7,
  pixelation: 1.5,
  sensitivity: 2.0,
  bloomBrightness: 0.2,
};

const SAT_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
  <line x1="2" y1="8" x2="14" y2="8" stroke="#00ff41" stroke-width="1.5"/>
  <line x1="8" y1="2" x2="8" y2="14" stroke="#00ff41" stroke-width="1.5"/>
  <circle cx="8" cy="8" r="2.5" fill="#001a00" stroke="#00ff41" stroke-width="1.2"/>
  <circle cx="8" cy="8" r="0.8" fill="#00ff41"/>
</svg>`)}`;


// Major world cities for globe labels
const WORLD_CITIES: { name: string; lat: number; lon: number }[] = [
  // Americas
  { name: 'Washington D.C.', lat: 38.907, lon: -77.037 },
  { name: 'New York', lat: 40.712, lon: -74.006 },
  { name: 'Los Angeles', lat: 34.052, lon: -118.243 },
  { name: 'Chicago', lat: 41.878, lon: -87.629 },
  { name: 'Toronto', lat: 43.651, lon: -79.347 },
  { name: 'Mexico City', lat: 19.432, lon: -99.133 },
  { name: 'Bogotá', lat: 4.711, lon: -74.072 },
  { name: 'Lima', lat: -12.046, lon: -77.043 },
  { name: 'São Paulo', lat: -23.550, lon: -46.633 },
  { name: 'Buenos Aires', lat: -34.603, lon: -58.381 },
  { name: 'Santiago', lat: -33.459, lon: -70.648 },
  { name: 'Caracas', lat: 10.480, lon: -66.904 },
  // Europe
  { name: 'London', lat: 51.507, lon: -0.128 },
  { name: 'Paris', lat: 48.856, lon: 2.352 },
  { name: 'Berlin', lat: 52.520, lon: 13.405 },
  { name: 'Madrid', lat: 40.416, lon: -3.703 },
  { name: 'Rome', lat: 41.902, lon: 12.496 },
  { name: 'Warsaw', lat: 52.229, lon: 21.012 },
  { name: 'Kyiv', lat: 50.450, lon: 30.523 },
  { name: 'Moscow', lat: 55.755, lon: 37.617 },
  { name: 'Istanbul', lat: 41.015, lon: 28.979 },
  { name: 'Stockholm', lat: 59.333, lon: 18.065 },
  { name: 'Amsterdam', lat: 52.374, lon: 4.890 },
  { name: 'Brussels', lat: 50.850, lon: 4.352 },
  // Middle East & Africa
  { name: 'Cairo', lat: 30.044, lon: 31.236 },
  { name: 'Riyadh', lat: 24.688, lon: 46.722 },
  { name: 'Dubai', lat: 25.204, lon: 55.270 },
  { name: 'Tel Aviv', lat: 32.085, lon: 34.782 },
  { name: 'Baghdad', lat: 33.338, lon: 44.394 },
  { name: 'Tehran', lat: 35.689, lon: 51.389 },
  { name: 'Nairobi', lat: -1.286, lon: 36.817 },
  { name: 'Lagos', lat: 6.524, lon: 3.380 },
  { name: 'Johannesburg', lat: -26.204, lon: 28.047 },
  { name: 'Addis Ababa', lat: 8.998, lon: 38.757 },
  { name: 'Kinshasa', lat: -4.322, lon: 15.322 },
  // Asia & Pacific
  { name: 'Beijing', lat: 39.904, lon: 116.407 },
  { name: 'Shanghai', lat: 31.230, lon: 121.473 },
  { name: 'Tokyo', lat: 35.689, lon: 139.692 },
  { name: 'Seoul', lat: 37.566, lon: 126.978 },
  { name: 'Delhi', lat: 28.613, lon: 77.209 },
  { name: 'Mumbai', lat: 19.076, lon: 72.877 },
  { name: 'Karachi', lat: 24.860, lon: 67.010 },
  { name: 'Dhaka', lat: 23.810, lon: 90.412 },
  { name: 'Bangkok', lat: 13.756, lon: 100.502 },
  { name: 'Jakarta', lat: -6.211, lon: 106.845 },
  { name: 'Singapore', lat: 1.352, lon: 103.820 },
  { name: 'Manila', lat: 14.599, lon: 120.984 },
  { name: 'Taipei', lat: 25.047, lon: 121.517 },
  { name: 'Kabul', lat: 34.528, lon: 69.172 },
  { name: 'Islamabad', lat: 33.729, lon: 73.094 },
  { name: 'Sydney', lat: -33.869, lon: 151.209 },
  { name: 'Melbourne', lat: -37.813, lon: 144.963 },
  { name: 'Canberra', lat: -35.280, lon: 149.130 },
  { name: 'Auckland', lat: -36.866, lon: 174.770 },
  { name: 'Pyongyang', lat: 39.019, lon: 125.738 },
  { name: 'Ulaanbaatar', lat: 47.886, lon: 106.906 },
  { name: 'Ankara', lat: 39.933, lon: 32.860 },
  { name: 'Tashkent', lat: 41.299, lon: 69.240 },
];

export default function WSR() {
  // Cesium refs
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<unknown>(null);
  const CsRef = useRef<typeof import('cesium') | null>(null);
  const satBbRef = useRef<unknown>(null);  // BillboardCollection - satellites (engine-external: TLE propagation)
  const orbitEntRef = useRef<unknown | null>(null); // tracked orbit polyline
  const postRef = useRef<Record<string, unknown>>({});
  const satRecordsRef = useRef<{ name: string; satrec: satelliteJs.SatRec }[]>([]);
  const propagationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const trackedIdRef = useRef<string | null>(null);
  const handlerRef = useRef<unknown>(null);
  const cameraHeightRef = useRef<number>(20000000);
  // Globe engine ref — owns all layer adapters and data source polling
  const engineRef = useRef<GlobeEngine | null>(null);
  // CCTV adapter ref — needed for altitude-gate updates
  const cctvAdapterRef = useRef<CCTVLayerAdapter | null>(null);

  // React state
  const [shaderMode, setShaderMode] = useState<ShaderMode>('normal');
  const [shaderParams, setShaderParams] = useState<ShaderParams>(DEFAULT_SHADER_PARAMS);
  const [layerVisibility, setLayerVisibility] = useState<Record<LayerId, boolean>>({
    satellites: true, flights: true, military: true, earthquakes: true, cctv: true,
  });
  const [detectionMode, setDetectionMode] = useState<DetectionMode>('sparse');
  const [cityIdx, setCityIdx] = useState(0); // Start at global Earth overview
  const [tracked, setTracked] = useState<TrackedEntity | null>(null);
  const [activeCCTV, setActiveCCTV] = useState<CCTVCamera | null>(null);
  const [cameraHeight, setCameraHeight] = useState<number>(20000000); // meters
  const [satCount, setSatCount] = useState(0);
  const [flightCount, setFlightCount] = useState(0);
  const [militaryCount, setMilitaryCount] = useState(0);
  const [quakeCount, setQuakeCount] = useState(0);
  const [cctvCount, setCctvCount] = useState(0);
  const [ready, setReady] = useState(false);
  const [diveFlash, setDiveFlash] = useState(false);

  const currentCity = CITIES[CITY_KEYS[cityIdx]];

  // ─── Initialize Cesium ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    let alive = true;

    async function boot() {
      (window as { CESIUM_BASE_URL?: string }).CESIUM_BASE_URL = '/cesium/';
      const Cesium = await import('cesium');
      await import('cesium/Build/Cesium/Widgets/widgets.css');
      if (!alive || !containerRef.current) return;
      CsRef.current = Cesium;

      const token = process.env.NEXT_PUBLIC_CESIUM_TOKEN;
      if (token) Cesium.Ion.defaultAccessToken = token;

      // Build viewer options
      const viewerEl = containerRef.current;
      type ViewerOptions = ConstructorParameters<typeof Cesium.Viewer>[1];
      const opts: ViewerOptions = {
        timeline: false, animation: false, baseLayerPicker: false,
        geocoder: false, homeButton: false, sceneModePicker: false,
        navigationHelpButton: false, fullscreenButton: false,
        infoBox: false, selectionIndicator: false,
        creditContainer: document.createElement('div'),
      };

      if (token) {
        opts.terrain = Cesium.Terrain.fromWorldTerrain();
      } else {
        opts.terrainProvider = new Cesium.EllipsoidTerrainProvider();
      }

      const viewer = new Cesium.Viewer(viewerEl, opts);

      // Cesium 1.121+ requires async factory for all imagery providers
      try {
        const esriProvider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
          'https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer',
          { credit: '© Esri World Imagery' }
        );
        viewer.imageryLayers.removeAll();
        viewer.imageryLayers.add(new Cesium.ImageryLayer(esriProvider));
      } catch (imgErr) {
        console.warn('ESRI imagery failed, trying OSM:', imgErr);
        try {
          const osmProvider = await Cesium.OpenStreetMapImageryProvider.fromUrl(
            'https://a.tile.openstreetmap.org/'
          );
          viewer.imageryLayers.removeAll();
          viewer.imageryLayers.add(new Cesium.ImageryLayer(osmProvider));
        } catch (e2) {
          console.warn('All imagery providers failed:', e2);
        }
      }
      viewerRef.current = viewer;

      // Aesthetic tweaks
      viewer.scene.backgroundColor = Cesium.Color.BLACK;
      if (viewer.scene.globe) {
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.nightFadeOutDistance = 0.0;
        viewer.scene.globe.nightFadeInDistance = 0.0;
      }
      viewer.scene.skyAtmosphere.show = true;

      // ── Mac trackpad / touchpad zoom fix ──────────────────────────────────
      const ctrl = viewer.scene.screenSpaceCameraController;
      ctrl.zoomEventTypes = [
        Cesium.CameraEventType.WHEEL,
        Cesium.CameraEventType.PINCH,
      ];
      ctrl.tiltEventTypes = [
        Cesium.CameraEventType.MIDDLE_DRAG,
        Cesium.CameraEventType.PINCH,
        { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL },
      ];
      ctrl.zoomFactor = 3.0;
      ctrl.enableCollisionDetection = true;

      // Modern browsers default wheel listeners to passive:true, which blocks
      // preventDefault() and lets the page intercept trackpad scroll before
      // Cesium sees it. Attach a non-passive listener on the canvas so Cesium
      // owns every wheel event.
      const canvas = viewer.scene.canvas as HTMLCanvasElement;
      const stopWheel = (e: Event) => { e.preventDefault(); };
      canvas.addEventListener('wheel', stopWheel, { passive: false });
      canvas.addEventListener('touchmove', stopWheel, { passive: false });
      canvas.style.touchAction = 'none';
      // Store for cleanup
      (canvas as HTMLCanvasElement & { _stopWheel?: EventListener })._stopWheel = stopWheel;

      // Start at Earth overview
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(0, 20, 22000000),
        orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 },
      });

      // Satellite billboard — kept engine-external (TLE propagation stays in WSR)
      satBbRef.current = viewer.scene.primitives.add(new Cesium.BillboardCollection({ scene: viewer.scene }));

      // ── Globe Engine boot ──────────────────────────────────────────────────
      // Build layer and data source adapters, register them with the engine,
      // then call engine.initialize() which:
      //   1. Injects the Cesium context into all adapters (analog to wire_services)
      //   2. Calls adapter.initialize() in registration order (analog to on_load)
      //   3. Starts polling timers for all data sources
      const cctvAdapter = new CCTVLayerAdapter();
      cctvAdapter.setAltitudeRef(() => cameraHeightRef.current);
      cctvAdapterRef.current = cctvAdapter;

      const engine = createGlobeEngine()
        // Static / structural layers
        .registerLayer(new BorderLayerAdapter())
        .registerLayer(new CityLabelAdapter(WORLD_CITIES))
        .registerLayer(new ConflictZoneAdapter())
        .registerLayer(cctvAdapter)
        // Real-time layers
        .registerLayer(new FlightLayerAdapter())
        .registerLayer(new MilitaryLayerAdapter())
        .registerLayer(new TheaterAircraftAdapter())
        .registerLayer(new EarthquakeLayerAdapter())
        // Data sources — each feeds its declared targetLayerIds
        .registerDataSource(new ConflictEventDataSource(['conflict-zone-layer']))
        .registerDataSource(new CCTVDataSource(['cctv-layer']))
        .registerDataSource(new FlightDataSource(['flight-layer']))
        .registerDataSource(new MilitaryDataSource(['military-layer']))
        .registerDataSource(new TheaterAircraftDataSource(['theater-aircraft-layer']))
        .registerDataSource(new EarthquakeDataSource(['earthquake-layer']));

      engineRef.current = engine;
      await engine.initialize(Cesium, viewer);

      // Subscribe to CCTV click events from the engine event bus
      engine.events.subscribeGlobal('cctv:open', (ev) => {
        const cam = ev.payload as CCTVCamera;
        if (cam) setActiveCCTV(cam);
      });

      // Wire entity counts from the engine event bus (adapters emit 'data:updated' after each update)
      engine.events.subscribeGlobal('data:updated', (ev) => {
        const { count } = ev.payload as { count: number };
        if (ev.layerId === 'flight-layer')    setFlightCount(count);
        if (ev.layerId === 'military-layer')  setMilitaryCount(count);
        if (ev.layerId === 'earthquake-layer') setQuakeCount(count);
        if (ev.layerId === 'cctv-layer')      setCctvCount(count);
      });

      setupPostProcessing(Cesium, viewer);
      setupClickHandler(Cesium, viewer);

      // Camera height — update ref on every render frame (cheap), React state at 2s interval
      viewer.scene.postRender.addEventListener(() => {
        cameraHeightRef.current = viewer.camera.positionCartographic?.height ?? 20000000;
      });

      setReady(true);
    }

    boot().catch(console.error);
    return () => {
      alive = false;
      if (propagationTimerRef.current) clearInterval(propagationTimerRef.current);
      postRef.current = {};
      // Engine teardown: stops all polling timers, tears down all layer adapters
      engineRef.current?.teardown();
      engineRef.current = null;
      cctvAdapterRef.current = null;
      const v = viewerRef.current as { isDestroyed?: () => boolean; destroy?: () => void; scene?: { canvas?: HTMLCanvasElement & { _stopWheel?: EventListener } } };
      if (v?.scene?.canvas?._stopWheel) {
        const c = v.scene.canvas;
        c.removeEventListener('wheel', c._stopWheel);
        c.removeEventListener('touchmove', c._stopWheel);
      }
      if (v && !v.isDestroyed?.()) v.destroy?.();
      viewerRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── Setup post-processing ───────────────────────────────────────────────
  function setupPostProcessing(Cesium: typeof import('cesium'), viewer: { postProcessStages: unknown }) {
    // Guard: don't add twice (can happen in React StrictMode)
    if (postRef.current.crt) return;

    const stages = viewer.postProcessStages as { add: (s: unknown) => unknown };

    try {
      postRef.current.crt = stages.add(new Cesium.PostProcessStage({
        name: 'wv_crt',
        fragmentShader: CRT_SHADER,
        uniforms: {
          scanlineIntensity: () => shaderParams.scanlineIntensity,
          pixelation: () => shaderParams.pixelation,
        },
      }));
      (postRef.current.crt as { enabled: boolean }).enabled = false;
    } catch (e) { console.warn('CRT stage skip:', e); }

    try {
      postRef.current.nvg = stages.add(Cesium.PostProcessStageLibrary.createNightVisionStage());
      (postRef.current.nvg as { enabled: boolean }).enabled = false;
    } catch (e) { console.warn('NVG stage skip:', e); }

    try {
      postRef.current.thermal = stages.add(new Cesium.PostProcessStage({
        name: 'wv_thermal',
        fragmentShader: THERMAL_SHADER,
      }));
      (postRef.current.thermal as { enabled: boolean }).enabled = false;
    } catch (e) { console.warn('Thermal stage skip:', e); }

    try {
      postRef.current.flare = stages.add(new Cesium.PostProcessStage({
        name: 'wv_flare',
        fragmentShader: FLARE_SHADER,
      }));
      (postRef.current.flare as { enabled: boolean }).enabled = false;
    } catch (e) { console.warn('Flare stage skip:', e); }

    // Bloom: use Cesium's built-in but it has a global name so only add once
    // We'll control brightness via the brightness uniform if it adds successfully
    try {
      const bloomStage = Cesium.PostProcessStageLibrary.createBloomStage();
      postRef.current.bloom = stages.add(bloomStage);
      (postRef.current.bloom as { enabled: boolean; uniforms: Record<string, unknown> }).enabled = false;
      const bu = (postRef.current.bloom as { uniforms?: Record<string, unknown> }).uniforms;
      if (bu) { bu.brightness = 0.1; bu.sigma = 2.5; bu.stepSize = 3.0; }
    } catch { /* Bloom unavailable in this context — skip */ }
  }

  // ─── Click handler ────────────────────────────────────────────────────────
  function setupClickHandler(Cesium: typeof import('cesium'), viewer: { scene: unknown }) {
    const scene = viewer.scene as { canvas: HTMLCanvasElement; pick: (pos: unknown) => unknown };
    const handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
    handlerRef.current = handler;

    handler.setInputAction((e: { position: unknown }) => {
      const picked = scene.pick(e.position);
      if (!picked) { setTracked(null); clearOrbit(); return; }

      const data = (picked as { id?: unknown }).id;
      if (data && typeof data === 'object' && (data as Record<string, unknown>)._wv) {
        const d = data as Record<string, unknown>;

        // CCTV camera click → emit to engine event bus → subscribed in boot()
        if (d.type === 'cctv') {
          engineRef.current?.events.publish({
            type: 'cctv:open',
            layerId: 'cctv-layer',
            payload: (d._camera ?? d) as unknown,
            timestamp: Date.now(),
          });
          return;
        }

        const entity: TrackedEntity = {
          id: d.id as string,
          name: d.name as string,
          type: d.type as TrackedEntity['type'],
          lat: d.lat as number,
          lon: d.lon as number,
          altitude: d.altitude as number,
          velocity: d.velocity as number,
          heading: d.heading as number,
          extra: d.extra as Record<string, string | number>,
        };
        setTracked(entity);
        trackedIdRef.current = entity.id;
        if (d.type === 'satellite') {
          drawOrbit(d.name as string);
          trackCamera(Cesium, viewer as { scene: unknown }, d.lat as number, d.lon as number, d.altitude as number);
        } else if (d.type === 'flight') {
          trackCamera(Cesium, viewer as { scene: unknown }, d.lat as number, d.lon as number, (d.altitude as number) + 50000);
        }
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  }

  function trackCamera(Cesium: typeof import('cesium'), viewer: { scene: unknown }, lat: number, lon: number, alt: number) {
    const v = viewerRef.current as { camera: { flyTo: (opts: unknown) => void } };
    if (!v) return;
    v.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, Math.max(alt + 500000, 800000)),
      duration: 2,
    });
  }

  function clearOrbit() {
    const v = viewerRef.current as { entities?: { remove: (e: unknown) => void } };
    if (orbitEntRef.current && v?.entities) {
      v.entities.remove(orbitEntRef.current);
      orbitEntRef.current = null;
    }
  }

  function drawOrbit(satName: string) {
    const Cesium = CsRef.current;
    const v = viewerRef.current as { entities?: { add: (e: unknown) => unknown } };
    if (!Cesium || !v?.entities) return;

    clearOrbit();
    const rec = satRecordsRef.current.find((r) => r.name === satName);
    if (!rec) return;

    const positions: unknown[] = [];
    const now = new Date();
    for (let min = 0; min < 95; min += 1) {
      const t = new Date(now.getTime() + min * 60000);
      const pv = satelliteJs.propagate(rec.satrec, t);
      if (!pv.position || typeof pv.position === 'boolean') continue;
      const gmst = satelliteJs.gstime(t);
      const geo = satelliteJs.eciToGeodetic(pv.position as satelliteJs.EciVec3<number>, gmst);
      positions.push(Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, geo.height * 1000));
    }

    if (positions.length < 2) return;
    orbitEntRef.current = v.entities.add({
      polyline: {
        positions,
        width: 1.2,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.15,
          color: Cesium.Color.fromCssColorString('#00ff41').withAlpha(0.6),
        }),
        clampToGround: false,
      },
    });
  }

  // ─── Shader mode changes ─────────────────────────────────────────────────
  useEffect(() => {
    const p = postRef.current;
    if (!p.crt) return; // Not yet initialized
    const setEnabled = (key: string, val: boolean) => {
      const s = p[key] as { enabled?: boolean } | undefined;
      if (s) s.enabled = val;
    };
    // Disable all effect stages first
    (['crt', 'nvg', 'thermal', 'flare'] as ShaderMode[]).forEach((m) => setEnabled(m, false));
    // Enable the active one
    if (shaderMode !== 'normal') setEnabled(shaderMode, true);
    // Bloom: on in normal/flare if brightness is set
    setEnabled('bloom', (shaderMode === 'normal' || shaderMode === 'flare') && shaderParams.bloomBrightness > 0.05);
  }, [shaderMode, shaderParams.bloomBrightness]);

  // ─── Satellite data + propagation ───────────────────────────────────────
  useEffect(() => {
    if (!ready) return;
    let alive = true;

    async function loadSatellites() {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
      const res = await fetch(`${apiBase}/api/satellites`).catch(() => null);
      if (!res?.ok || !alive) return;
      const records: SatelliteRecord[] = await res.json();
      setSatCount(records.length);

      satRecordsRef.current = records
        .map((r) => {
          try { return { name: r.name, satrec: satelliteJs.twoline2satrec(r.line1, r.line2) }; }
          catch { return null; }
        })
        .filter(Boolean) as { name: string; satrec: satelliteJs.SatRec }[];

      startPropagation();
    }

    function startPropagation() {
      if (propagationTimerRef.current) clearInterval(propagationTimerRef.current);
      propagationTimerRef.current = setInterval(updateSatellitePositions, 3000);
      updateSatellitePositions();
    }

    loadSatellites();
    return () => { alive = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  const updateSatellitePositions = useCallback(() => {
    const Cesium = CsRef.current;
    const bb = satBbRef.current as {
      removeAll: () => void;
      add: (opts: unknown) => unknown;
      show: boolean;
    };
    if (!Cesium || !bb) return;

    bb.show = layerVisibility.satellites;
    if (!layerVisibility.satellites) return;

    const records = satRecordsRef.current;
    const limit = detectionMode === 'sparse' ? Math.min(300, records.length) : records.length;
    const sample = detectionMode === 'sparse'
      ? records.filter((_, i) => i % Math.ceil(records.length / limit) === 0)
      : records;

    bb.removeAll();
    const now = new Date();
    const gmst = satelliteJs.gstime(now);

    let tracked: TrackedEntity | null = null;

    for (const rec of sample) {
      try {
        const pv = satelliteJs.propagate(rec.satrec, now);
        if (!pv.position || typeof pv.position === 'boolean') continue;
        const geo = satelliteJs.eciToGeodetic(pv.position as satelliteJs.EciVec3<number>, gmst);
        const lat = satelliteJs.degreesLong(geo.latitude);
        const lon = satelliteJs.degreesLong(geo.longitude);
        const altM = geo.height * 1000;

        const isTracked = rec.name === trackedIdRef.current;
        if (isTracked) {
          tracked = { id: rec.name, name: rec.name, type: 'satellite', lat, lon, altitude: altM };
        }

        bb.add({
          position: Cesium.Cartesian3.fromRadians(geo.longitude, geo.latitude, altM),
          image: SAT_ICON,
          width: isTracked ? 18 : 10,
          height: isTracked ? 18 : 10,
          color: isTracked
            ? Cesium.Color.fromCssColorString('#ffffff')
            : Cesium.Color.fromCssColorString('#00ff41').withAlpha(0.8),
          id: {
            _wv: true, id: rec.name, name: rec.name, type: 'satellite',
            lat, lon, altitude: altM, velocity: 0, heading: 0, extra: {},
          },
        });
      } catch { /* skip bad TLE */ }
    }

    if (tracked && trackedIdRef.current) {
      setTracked((prev) => prev ? { ...prev, ...tracked! } : tracked);
    }
  }, [layerVisibility.satellites, detectionMode]);

  // ─── Camera height polling → drives zoom-level state + CCTV altitude gate ─
  useEffect(() => {
    if (!ready) return;
    const timer = setInterval(() => {
      const h = cameraHeightRef.current;
      setCameraHeight((prev) => Math.abs(prev - h) > 5000 ? h : prev);
      // Notify CCTV adapter of altitude change (altitude-gated display)
      cctvAdapterRef.current?.refreshAltitudeGate();
    }, 1500);
    return () => clearInterval(timer);
  }, [ready]);

  // ─── Layer visibility → engine.setLayerVisible() ──────────────────────────
  useEffect(() => {
    const bb = satBbRef.current as { show: boolean } | null;
    if (bb) bb.show = layerVisibility.satellites;
  }, [layerVisibility.satellites]);

  useEffect(() => {
    engineRef.current?.setLayerVisible('flight-layer', layerVisibility.flights);
  }, [layerVisibility.flights]);

  useEffect(() => {
    engineRef.current?.setLayerVisible('military-layer', layerVisibility.military);
  }, [layerVisibility.military]);

  useEffect(() => {
    engineRef.current?.setLayerVisible('earthquake-layer', layerVisibility.earthquakes);
  }, [layerVisibility.earthquakes]);

  useEffect(() => {
    engineRef.current?.setLayerVisible('cctv-layer', layerVisibility.cctv);
    cctvAdapterRef.current?.refreshAltitudeGate();
  }, [layerVisibility.cctv]);

  // ─── Keyboard handler (shader + POI) ────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      const Cesium = CsRef.current;
      const v = viewerRef.current as { camera?: { flyTo: (o: unknown) => void } };

      // Shader mode keys
      if (e.key === '1') setShaderMode('normal');
      if (e.key === '2') setShaderMode('crt');
      if (e.key === '3') setShaderMode('nvg');
      if (e.key === '4') setShaderMode('thermal');
      if (e.key === '5') setShaderMode('flare');

      // POI keys q w e r t
      if (Cesium && v?.camera && ['q','w','e','r','t'].includes(e.key.toLowerCase())) {
        const pois = currentCity.landmarks;
        const poi = pois.find((p) => p.key === e.key.toLowerCase());
        if (poi) {
          v.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(poi.lon, poi.lat, poi.alt),
            orientation: {
              heading: Cesium.Math.toRadians(poi.heading),
              pitch: Cesium.Math.toRadians(poi.pitch),
              roll: 0,
            },
            duration: 2.5,
          });
        }
      }

      // SPACE — dive camera toward the globe point under the crosshair (screen center)
      if (e.key === ' ') {
        e.preventDefault();
        const viewer = viewerRef.current as {
          camera: {
            flyTo: (o: unknown) => void;
            getPickRay: (p: unknown) => unknown;
            heading: number;
          };
          scene: {
            canvas: HTMLCanvasElement;
            globe: { pick: (ray: unknown, scene: unknown) => unknown };
          };
        } | null;
        if (!Cesium || !viewer) return;

        const canvas = viewer.scene.canvas;
        const screenCenter = new Cesium.Cartesian2(
          canvas.clientWidth / 2,
          canvas.clientHeight / 2,
        );

        let worldPos: unknown;
        try {
          const ray = viewer.camera.getPickRay(screenCenter);
          worldPos = ray ? viewer.scene.globe.pick(ray, viewer.scene) : undefined;
        } catch { /* crosshair pointed at sky — no-op */ }

        if (!worldPos || !Cesium.defined(worldPos)) return;

        const carto = Cesium.Ellipsoid.WGS84.cartesianToCartographic(
          worldPos as import('cesium').Cartesian3,
        );
        const lat = Cesium.Math.toDegrees(carto.latitude);
        const lon = Cesium.Math.toDegrees(carto.longitude);
        const targetAlt = Math.max(500, cameraHeightRef.current * 0.03);

        viewer.camera.flyTo({
          destination: Cesium.Cartesian3.fromDegrees(lon, lat, targetAlt),
          orientation: {
            heading: viewer.camera.heading,
            pitch: Cesium.Math.toRadians(-30),
            roll: 0,
          },
          duration: 2.5,
        });

        setDiveFlash(true);
        setTimeout(() => setDiveFlash(false), 700);
      }

      // City selector 1-6 handled above; also arrow keys
      if (e.key === 'Escape') { setTracked(null); trackedIdRef.current = null; clearOrbit(); }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentCity]);

  // ─── City change: fly to first POI ───────────────────────────────────────
  useEffect(() => {
    const Cesium = CsRef.current;
    const v = viewerRef.current as { camera?: { flyTo: (o: unknown) => void } } | null;
    if (!Cesium || !v?.camera || !ready) return;
    const poi = currentCity.landmarks[0];
    v.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(poi.lon, poi.lat, poi.alt),
      orientation: {
        heading: Cesium.Math.toRadians(poi.heading),
        pitch: Cesium.Math.toRadians(poi.pitch),
        roll: 0,
      },
      duration: 3.5,
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cityIdx, ready]);

  // ─── Handlers ────────────────────────────────────────────────────────────
  const handleLayerToggle = (layer: LayerId) => {
    setLayerVisibility((prev) => ({ ...prev, [layer]: !prev[layer] }));
  };

  const handleShaderParamChange = (key: keyof ShaderParams, value: number) => {
    setShaderParams((prev) => ({ ...prev, [key]: value }));
    // Update uniform live if relevant stage exists
    const stage = postRef.current[key === 'bloomBrightness' ? 'bloom' : 'crt'] as { uniforms?: Record<string, unknown> };
    if (stage?.uniforms) {
      if (key === 'bloomBrightness') stage.uniforms.brightness = value;
    }
  };

  // ─── Quick flyTo for Intel panel ─────────────────────────────────────────
  const flyToLatLon = useCallback((lat: number, lon: number, alt = 200000) => {
    const Cesium = CsRef.current;
    const v = viewerRef.current as { camera?: { flyTo: (o: unknown) => void } } | null;
    if (!Cesium || !v?.camera) return;
    v.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, alt),
      orientation: { heading: 0, pitch: Cesium.Math.toRadians(-60), roll: 0 },
      duration: 2.5,
    });
  }, []);

  // ─── Geocoder flyTo ───────────────────────────────────────────────────────
  const flyToResult = useCallback((r: GeoResult) => {
    const Cesium = CsRef.current;
    const v = viewerRef.current as { camera?: { flyTo: (o: unknown) => void } } | null;
    if (!Cesium || !v?.camera) return;

    // Compute altitude from bounding box; cap at 18Mm (beyond that Earth fits anyway)
    const bbox = r.boundingBox;
    let alt = 200000;
    if (bbox) {
      const latSpan = Math.abs(bbox[1] - bbox[0]);
      const lonSpan = Math.abs(bbox[3] - bbox[2]);
      const span = Math.max(latSpan, lonSpan);
      // 111km/deg, ×2 for context padding, cap at 18Mm
      alt = Math.max(500, Math.min(span * 111000 * 2.0, 18000000));
    }

    // Pitch: Cesium convention — 0° = horizontal, -90° = straight down (nadir).
    // At orbital altitude, we must look nearly straight down: Earth's limb is only
    // ~15° away from the nadir, so any large forward tilt sends the camera past Earth.
    // Formula: pitch = -(90° - forwardTilt), where forwardTilt shrinks with altitude.
    //   • forwardTilt = 0  → pitch = -90° (pure nadir, target centred)
    //   • forwardTilt = 30 → pitch = -60° (nice angled city view)
    //   • forwardTilt = 50 → pitch = -40° (street-level oblique)
    const forwardTiltDeg =
      alt > 2000000  ?  2 :   // orbital / continental — nearly straight down
      alt > 300000   ?  8 :   // regional
      alt > 30000    ? 20 :   // city
      alt > 3000     ? 30 :   // district
                       45;    // street — nice oblique

    const pitchClamped = -(90 - forwardTiltDeg);

    v.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(r.lon, r.lat, alt),
      orientation: {
        heading: 0,
        pitch: Cesium.Math.toRadians(pitchClamped),
        roll: 0,
      },
      duration: 3,
    });
  }, []);

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      {/* Cesium canvas — touch-action:none prevents browser from swallowing trackpad/pinch events */}
      <div ref={containerRef} className="absolute inset-0" style={{ touchAction: 'none' }} />

      {/* Crosshair — flashes bright on Space-dive */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-10">
        <svg
          width="40" height="40" viewBox="0 0 40 40" fill="none"
          style={{
            opacity: diveFlash ? 1 : 0.4,
            transition: 'opacity 0.15s ease',
            filter: diveFlash ? 'drop-shadow(0 0 6px #00ff41)' : 'none',
          }}
        >
          <circle cx="20" cy="20" r="8" stroke="#00ff41" strokeWidth={diveFlash ? 1.5 : 0.8} />
          <line x1="20" y1="0" x2="20" y2="12" stroke="#00ff41" strokeWidth={diveFlash ? 1.5 : 0.8} />
          <line x1="20" y1="28" x2="20" y2="40" stroke="#00ff41" strokeWidth={diveFlash ? 1.5 : 0.8} />
          <line x1="0" y1="20" x2="12" y2="20" stroke="#00ff41" strokeWidth={diveFlash ? 1.5 : 0.8} />
          <line x1="28" y1="20" x2="40" y2="20" stroke="#00ff41" strokeWidth={diveFlash ? 1.5 : 0.8} />
        </svg>
      </div>

      {/* Corner brackets */}
      <div className="absolute inset-0 pointer-events-none z-10">
        {[['top-2 left-2', 'border-t border-l'], ['top-2 right-2', 'border-t border-r'],
          ['bottom-2 left-2', 'border-b border-l'], ['bottom-2 right-2', 'border-b border-r']].map(([pos, border]) => (
          <div key={pos} className={`absolute ${pos} w-6 h-6 ${border} border-green-500/40`} />
        ))}
      </div>

      {/* Status bar — search embedded in center */}
      <StatusBar
        shaderMode={shaderMode}
        layerVisibility={layerVisibility}
        onSelect={flyToResult}
      />

      {/* Intel ticker — full-width strip pinned below navbar (top-9 = 36px = h-9) */}
      <IntelTicker />

      {/* Left panel: Data layers + Intel — top-[60px] clears navbar (36px) + ticker (24px) */}
      <div className="absolute left-4 top-[60px] z-20 w-52 flex flex-col gap-2">
        <DataLayerPanel
          visibility={layerVisibility}
          onToggle={handleLayerToggle}
          detectionMode={detectionMode}
          onDetectionChange={setDetectionMode}
          cameraHeight={cameraHeight}
          counts={{ satellites: satCount, flights: flightCount, military: militaryCount, earthquakes: quakeCount, cctv: cctvCount }}
        />
        <IntelPanel onFlyTo={flyToLatLon} />
      </div>

      {/* Right panel: Shader controls */}
      <div className="absolute right-4 top-[60px] z-20 w-64">
        <ShaderPanel
          mode={shaderMode}
          params={shaderParams}
          onModeChange={setShaderMode}
          onParamChange={handleShaderParamChange}
        />
      </div>

      {/* Tracking overlay */}
      {tracked && (
        <div className="absolute right-4 top-40 z-20 w-64">
          <TrackingOverlay entity={tracked} onClose={() => { setTracked(null); trackedIdRef.current = null; clearOrbit(); }} />
        </div>
      )}

      {/* CCTV live feed panel */}
      {activeCCTV && (
        <CCTVPanel key={activeCCTV.id} camera={activeCCTV} onClose={() => setActiveCCTV(null)} />
      )}

      {/* Zoom level indicator */}
      <div className="absolute bottom-12 left-1/2 -translate-x-1/2 z-20 font-mono text-[10px] text-green-500/40 tracking-widest">
        {cameraHeight > 8000000 ? 'GLOBAL · ORBIT' :
         cameraHeight > 2000000 ? 'CONTINENTAL' :
         cameraHeight > 300000  ? 'REGIONAL' :
         cameraHeight > 30000   ? 'CITY · CLICK FLIGHTS TO TRACK' :
         cameraHeight > 3000    ? 'DISTRICT · CCTV CAMERAS VISIBLE' :
                                  'STREET LEVEL · CLICK ▦ FOR CCTV FEED'}
      </div>

      {/* ── Zoom controls — bottom right ─────────────────────────────────── */}
      <div className="absolute bottom-12 right-4 z-20 flex flex-col gap-1">
        {/* Zoom In */}
        <button
          onClick={() => {
            const v = viewerRef.current as { camera?: { zoomIn: (a: number) => void } } | null;
            if (v?.camera) v.camera.zoomIn(cameraHeight * 0.4);
          }}
          className="w-9 h-9 border border-green-500/30 bg-black/80 text-green-400 font-mono text-lg leading-none flex items-center justify-center hover:border-green-400/60 hover:text-green-300 hover:bg-green-950/40 transition-all select-none"
          title="Zoom In"
        >+</button>

        {/* Home — reset to Earth overview */}
        <button
          onClick={() => {
            const Cesium = CsRef.current;
            const v = viewerRef.current as { camera?: { flyTo: (o: unknown) => void } } | null;
            if (!Cesium || !v?.camera) return;
            v.camera.flyTo({
              destination: Cesium.Cartesian3.fromDegrees(0, 20, 22000000),
              orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 },
              duration: 2,
            });
          }}
          className="w-9 h-9 border border-green-500/20 bg-black/80 text-green-500/50 font-mono text-[10px] leading-none flex items-center justify-center hover:border-green-400/50 hover:text-green-400 hover:bg-green-950/30 transition-all select-none tracking-tighter"
          title="Reset to Earth overview"
        >⌂</button>

        {/* Fly to Middle East Theater */}
        <button
          onClick={() => {
            const Cesium = CsRef.current;
            const v = viewerRef.current as { camera?: { flyTo: (o: unknown) => void } } | null;
            if (!Cesium || !v?.camera) return;
            v.camera.flyTo({
              destination: Cesium.Cartesian3.fromDegrees(40, 30, 4000000),
              orientation: { heading: 0, pitch: Cesium.Math.toRadians(-70), roll: 0 },
              duration: 2.5,
            });
          }}
          className="w-9 h-9 border border-orange-500/40 bg-black/80 text-orange-400/70 font-mono text-[9px] leading-none flex items-center justify-center hover:border-orange-400/70 hover:text-orange-300 hover:bg-orange-950/30 transition-all select-none tracking-tighter"
          title="Fly to Middle East Theater"
        >⚠</button>

        {/* Zoom Out */}
        <button
          onClick={() => {
            const v = viewerRef.current as { camera?: { zoomOut: (a: number) => void } } | null;
            if (v?.camera) v.camera.zoomOut(cameraHeight * 0.6);
          }}
          className="w-9 h-9 border border-green-500/30 bg-black/80 text-green-400 font-mono text-lg leading-none flex items-center justify-center hover:border-green-400/60 hover:text-green-300 hover:bg-green-950/40 transition-all select-none"
          title="Zoom Out"
        >−</button>
      </div>

      {/* Loading state */}
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center z-30 bg-black">
          <div className="font-mono text-green-400 text-sm space-y-2 text-center">
            <div className="text-2xl tracking-widest animate-pulse">◉ WORLD SITUATION ROOM</div>
            <div className="text-green-500/60 tracking-widest text-xs">INITIALIZING GEOSPATIAL ENGINE...</div>
          </div>
        </div>
      )}

      {/* Bottom hint */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 font-mono text-[10px] text-green-500/25 text-center space-y-0.5">
        <div>Click satellite / flight / earthquake to track &nbsp;·&nbsp; Click <span className="text-pink-400/40">▦</span> camera icon for live CCTV feed</div>
        <div><span className="text-green-400/30">SPACE</span> · Dive to crosshair &nbsp;·&nbsp; <span className="text-green-400/30">ESC</span> · Release track</div>
      </div>
    </div>
  );
}
