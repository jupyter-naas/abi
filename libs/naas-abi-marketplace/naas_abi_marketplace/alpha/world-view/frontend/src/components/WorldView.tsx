'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import * as satelliteJs from 'satellite.js';
import type { ShaderMode, LayerId, DetectionMode, TrackedEntity, ShaderParams, SatelliteRecord, FlightState, EarthquakeFeature, CCTVCamera } from '@/lib/types';
import { CRT_SHADER, THERMAL_SHADER, FLARE_SHADER } from '@/lib/shaders';
import { CITIES, CITY_KEYS } from '@/data/landmarks';
import StatusBar from './ui/StatusBar';
import ShaderPanel from './ui/ShaderPanel';
import DataLayerPanel from './ui/DataLayerPanel';
import TrackingOverlay from './ui/TrackingOverlay';
import CCTVPanel from './ui/CCTVPanel';
import GeoSearch, { type GeoResult } from './ui/GeoSearch';

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

const FLIGHT_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <polygon points="7,1 9,6 13,7 9,8 7,13 5,8 1,7 5,6" fill="#00cfff" opacity="0.9"/>
</svg>`)}`;

const MIL_FLIGHT_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
  <polygon points="7,1 9,6 13,7 9,8 7,13 5,8 1,7 5,6" fill="#ff8800" opacity="0.95"/>
</svg>`)}`;

const CCTV_ICON = `data:image/svg+xml,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">
  <rect x="1" y="5" width="11" height="8" rx="1" fill="none" stroke="#ff3366" stroke-width="1.5"/>
  <polygon points="12,7 17,5 17,13 12,11" fill="#ff3366" opacity="0.85"/>
  <circle cx="5" cy="9" r="1.5" fill="#ff3366"/>
  <line x1="1" y1="2" x2="3" y2="5" stroke="#ff3366" stroke-width="1.2"/>
</svg>`)}`;

export default function WorldView() {
  // Cesium refs
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<unknown>(null);
  const CsRef = useRef<typeof import('cesium') | null>(null);
  const satBbRef = useRef<unknown>(null);  // BillboardCollection - satellites
  const fltBbRef = useRef<unknown>(null);  // BillboardCollection - flights
  const milBbRef = useRef<unknown>(null);  // BillboardCollection - military
  const cctvBbRef = useRef<unknown>(null); // BillboardCollection - CCTV cameras
  const quakeEntRef = useRef<unknown[]>([]);  // earthquake entities
  const orbitEntRef = useRef<unknown | null>(null); // tracked orbit polyline
  const postRef = useRef<Record<string, unknown>>({});
  const satRecordsRef = useRef<{ name: string; satrec: satelliteJs.SatRec }[]>([]);
  const propagationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const flightDataRef = useRef<FlightState[]>([]);
  const milDataRef = useRef<FlightState[]>([]);
  const cctvDataRef = useRef<CCTVCamera[]>([]);
  const trackedIdRef = useRef<string | null>(null);
  const handlerRef = useRef<unknown>(null);
  const cameraHeightRef = useRef<number>(20000000);

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
  const [ready, setReady] = useState(false);

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
      // Enable all zoom event types including PINCH (two-finger) and WHEEL
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
      // Faster zoom response for Mac trackpad (default 5.0 is too slow)
      ctrl.zoomFactor = 3.0;
      // Allow smooth inertia
      ctrl.enableCollisionDetection = true;

      // Start at Earth overview
      viewer.camera.setView({
        destination: Cesium.Cartesian3.fromDegrees(0, 20, 22000000),
        orientation: { heading: 0, pitch: -Cesium.Math.PI_OVER_TWO, roll: 0 },
      });

      // Primitive collections
      satBbRef.current = viewer.scene.primitives.add(new Cesium.BillboardCollection({ scene: viewer.scene }));
      fltBbRef.current = viewer.scene.primitives.add(new Cesium.BillboardCollection({ scene: viewer.scene }));
      milBbRef.current = viewer.scene.primitives.add(new Cesium.BillboardCollection({ scene: viewer.scene }));
      cctvBbRef.current = viewer.scene.primitives.add(new Cesium.BillboardCollection({ scene: viewer.scene }));

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
      // Reset post-process refs so guard works on StrictMode remount with fresh viewer
      postRef.current = {};
      const v = viewerRef.current as { isDestroyed?: () => boolean; destroy?: () => void };
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

        // CCTV camera click → open feed panel
        if (d.type === 'cctv') {
          const cam = cctvDataRef.current.find((c) => c.id === d.id);
          if (cam) setActiveCCTV(cam);
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
      const res = await fetch('/api/satellites').catch(() => null);
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

  // ─── Flight data ─────────────────────────────────────────────────────────
  const fetchFlights = useCallback(async () => {
    const Cesium = CsRef.current;
    const bb = fltBbRef.current as { removeAll: () => void; add: (o: unknown) => void; show: boolean } | null;
    if (!Cesium || !bb) return;

    try {
      const res = await fetch('/api/flights');
      if (!res.ok) return;
      const flights: FlightState[] = await res.json();
      flightDataRef.current = flights;
      setFlightCount(flights.length);

      bb.show = layerVisibility.flights;
      if (!layerVisibility.flights) return;
      bb.removeAll();

      for (const f of flights) {
        if (f.onGround || f.lat == null || f.lon == null) continue;
        bb.add({
          position: Cesium.Cartesian3.fromDegrees(f.lon, f.lat, Math.max(f.altitude, 100)),
          image: FLIGHT_ICON,
          width: 10,
          height: 10,
          rotation: -Cesium.Math.toRadians(f.heading),
          alignedAxis: Cesium.Cartesian3.UNIT_Z,
          color: Cesium.Color.fromCssColorString('#00cfff').withAlpha(0.85),
          id: {
            _wv: true, id: f.icao24, name: f.callsign, type: 'flight',
            lat: f.lat, lon: f.lon, altitude: f.altitude,
            velocity: f.velocity, heading: f.heading, extra: {},
          },
        });
      }
    } catch { /* no-op */ }
  }, [layerVisibility.flights]);

  const fetchMilitary = useCallback(async () => {
    const Cesium = CsRef.current;
    const bb = milBbRef.current as { removeAll: () => void; add: (o: unknown) => void; show: boolean } | null;
    if (!Cesium || !bb) return;

    try {
      const res = await fetch('/api/military');
      if (!res.ok) return;
      const flights: FlightState[] = await res.json();
      milDataRef.current = flights;
      setMilitaryCount(flights.length);

      bb.show = layerVisibility.military;
      if (!layerVisibility.military) return;
      bb.removeAll();

      for (const f of flights) {
        if (f.lat == null || f.lon == null) continue;
        bb.add({
          position: Cesium.Cartesian3.fromDegrees(f.lon, f.lat, Math.max(f.altitude, 500)),
          image: MIL_FLIGHT_ICON,
          width: 12,
          height: 12,
          rotation: -Cesium.Math.toRadians(f.heading),
          alignedAxis: Cesium.Cartesian3.UNIT_Z,
          color: Cesium.Color.fromCssColorString('#ff8800').withAlpha(0.9),
          id: {
            _wv: true, id: f.icao24, name: f.callsign, type: 'flight',
            lat: f.lat, lon: f.lon, altitude: f.altitude,
            velocity: f.velocity, heading: f.heading, extra: { isMilitary: 1 },
          },
        });
      }
    } catch { /* no-op */ }
  }, [layerVisibility.military]);

  // ─── Earthquake data ─────────────────────────────────────────────────────
  const fetchEarthquakes = useCallback(async () => {
    const Cesium = CsRef.current;
    const v = viewerRef.current as { entities?: { add: (e: unknown) => unknown; remove: (e: unknown) => void } };
    if (!Cesium || !v?.entities) return;

    try {
      const res = await fetch('/api/earthquakes');
      if (!res.ok) return;
      const quakes: EarthquakeFeature[] = await res.json();
      setQuakeCount(quakes.length);

      quakeEntRef.current.forEach((e) => v.entities?.remove(e));
      quakeEntRef.current = [];

      if (!layerVisibility.earthquakes) return;

      for (const q of quakes) {
        const radius = Math.max(30000, q.mag * 60000);
        const color = q.mag >= 6 ? '#ff2200' : q.mag >= 4 ? '#ff6600' : '#ffaa00';
        const ent = v.entities.add({
          position: Cesium.Cartesian3.fromDegrees(q.lon, q.lat, 0),
          ellipse: {
            semiMinorAxis: radius,
            semiMajorAxis: radius,
            height: 0,
            material: Cesium.Color.fromCssColorString(color).withAlpha(0.3),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString(color).withAlpha(0.8),
          },
          id: {
            _wv: true, id: q.id, name: `M${q.mag} – ${q.place}`, type: 'earthquake',
            lat: q.lat, lon: q.lon, altitude: -q.depth * 1000,
            velocity: 0, heading: 0, extra: { magnitude: q.mag, depth_km: q.depth },
          },
        });
        quakeEntRef.current.push(ent);
      }
    } catch { /* no-op */ }
  }, [layerVisibility.earthquakes]);

  // ─── CCTV layer ───────────────────────────────────────────────────────────
  const updateCCTVBillboards = useCallback(() => {
    const Cesium = CsRef.current;
    const bb = cctvBbRef.current as { removeAll: () => void; add: (o: unknown) => void; show: boolean } | null;
    if (!Cesium || !bb) return;

    const height = cameraHeightRef.current;
    // Only show CCTV cameras when zoomed below 15km altitude
    const shouldShow = layerVisibility.cctv && height < 15000000;
    bb.show = shouldShow;
    if (!shouldShow) return;

    bb.removeAll();
    const cameras = cctvDataRef.current;
    const iconSz = height < 5000 ? 22 : height < 50000 ? 18 : 14;
    for (const cam of cameras) {
      bb.add({
        position: Cesium.Cartesian3.fromDegrees(cam.lon, cam.lat, 5),
        image: CCTV_ICON,
        width: iconSz,
        height: iconSz,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        id: { _wv: true, id: cam.id, name: cam.name, type: 'cctv', lat: cam.lat, lon: cam.lon, altitude: 5 },
      });
    }
  }, [layerVisibility.cctv]);

  const fetchCCTV = useCallback(async () => {
    try {
      const res = await fetch('/api/cctv');
      if (!res.ok) return;
      const cameras: CCTVCamera[] = await res.json();
      cctvDataRef.current = cameras;
      updateCCTVBillboards();
    } catch { /* no-op */ }
  }, [updateCCTVBillboards]);

  // ─── Camera height polling → drives zoom-level state ─────────────────────
  useEffect(() => {
    if (!ready) return;
    const timer = setInterval(() => {
      const h = cameraHeightRef.current;
      setCameraHeight((prev) => Math.abs(prev - h) > 5000 ? h : prev);
      updateCCTVBillboards();
    }, 1500);
    return () => clearInterval(timer);
  }, [ready, updateCCTVBillboards]);

  // ─── Polling ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!ready) return;
    fetchFlights();
    fetchMilitary();
    fetchEarthquakes();
    fetchCCTV();
    const fi = setInterval(fetchFlights, 30000);
    const mi = setInterval(fetchMilitary, 60000);
    const qi = setInterval(fetchEarthquakes, 300000);
    const ci = setInterval(fetchCCTV, 300000);  // refresh CCTV list every 5 min
    return () => { clearInterval(fi); clearInterval(mi); clearInterval(qi); clearInterval(ci); };
  }, [ready, fetchFlights, fetchMilitary, fetchEarthquakes, fetchCCTV]);

  // ─── Layer visibility changes ─────────────────────────────────────────────
  useEffect(() => {
    const bb = satBbRef.current as { show: boolean } | null;
    if (bb) bb.show = layerVisibility.satellites;
  }, [layerVisibility.satellites]);

  useEffect(() => {
    const bb = fltBbRef.current as { show: boolean } | null;
    if (bb) bb.show = layerVisibility.flights;
    if (ready && layerVisibility.flights) fetchFlights();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layerVisibility.flights, ready]);

  useEffect(() => {
    const bb = milBbRef.current as { show: boolean } | null;
    if (bb) bb.show = layerVisibility.military;
    if (ready && layerVisibility.military) fetchMilitary();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layerVisibility.military, ready]);

  useEffect(() => {
    if (ready) fetchEarthquakes();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layerVisibility.earthquakes, ready]);

  useEffect(() => {
    updateCCTVBillboards();
  }, [layerVisibility.cctv, updateCCTVBillboards]);

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

      {/* Crosshair */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-10">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity={0.4}>
          <circle cx="20" cy="20" r="8" stroke="#00ff41" strokeWidth="0.8" />
          <line x1="20" y1="0" x2="20" y2="12" stroke="#00ff41" strokeWidth="0.8" />
          <line x1="20" y1="28" x2="20" y2="40" stroke="#00ff41" strokeWidth="0.8" />
          <line x1="0" y1="20" x2="12" y2="20" stroke="#00ff41" strokeWidth="0.8" />
          <line x1="28" y1="20" x2="40" y2="20" stroke="#00ff41" strokeWidth="0.8" />
        </svg>
      </div>

      {/* Corner brackets */}
      <div className="absolute inset-0 pointer-events-none z-10">
        {[['top-2 left-2', 'border-t border-l'], ['top-2 right-2', 'border-t border-r'],
          ['bottom-2 left-2', 'border-b border-l'], ['bottom-2 right-2', 'border-b border-r']].map(([pos, border]) => (
          <div key={pos} className={`absolute ${pos} w-6 h-6 ${border} border-green-500/40`} />
        ))}
      </div>

      {/* Status bar */}
      <StatusBar
        shaderMode={shaderMode}
        satCount={satCount}
        flightCount={flightCount}
        militaryCount={militaryCount}
        quakeCount={quakeCount}
        layerVisibility={layerVisibility}
        cityName={currentCity.name}
      />

      {/* ── Geocoder search bar — top-center ─────────────────────────────── */}
      <div className="absolute top-10 left-1/2 -translate-x-1/2 z-30">
        <GeoSearch onSelect={flyToResult} />
      </div>

      {/* Left panel: Data layers */}
      <div className="absolute left-4 top-12 z-20 w-52">
        <DataLayerPanel
          visibility={layerVisibility}
          onToggle={handleLayerToggle}
          detectionMode={detectionMode}
          onDetectionChange={setDetectionMode}
          cameraHeight={cameraHeight}
        />
      </div>

      {/* Right panel: Shader controls */}
      <div className="absolute right-4 top-12 z-20 w-64">
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
        <CCTVPanel camera={activeCCTV} onClose={() => setActiveCCTV(null)} />
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

      {/* Loading state */}
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center z-30 bg-black">
          <div className="font-mono text-green-400 text-sm space-y-2 text-center">
            <div className="text-2xl tracking-widest animate-pulse">◉ WORLDVIEW</div>
            <div className="text-green-500/60 tracking-widest text-xs">INITIALIZING GEOSPATIAL ENGINE...</div>
          </div>
        </div>
      )}

      {/* Bottom hint */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 font-mono text-[10px] text-green-500/25 text-center space-y-0.5">
        <div>Click satellite / flight / earthquake to track &nbsp;·&nbsp; Click <span className="text-pink-400/40">▦</span> camera icon for live CCTV feed</div>
      </div>
    </div>
  );
}
