export type ShaderMode = 'normal' | 'crt' | 'nvg' | 'thermal' | 'flare';
export type LayerId = 'satellites' | 'flights' | 'military' | 'earthquakes' | 'cctv';
export type DetectionMode = 'sparse' | 'full';

export interface SatelliteRecord {
  name: string;
  line1: string;
  line2: string;
}

export interface FlightState {
  icao24: string;
  callsign: string;
  lat: number;
  lon: number;
  altitude: number;
  velocity: number;
  heading: number;
  onGround: boolean;
  isMilitary?: boolean;
}

export interface EarthquakeFeature {
  id: string;
  mag: number;
  place: string;
  lat: number;
  lon: number;
  depth: number;
  time: number;
}

export interface CCTVCamera {
  id: string;
  name: string;
  lat: number;
  lon: number;
  city: string;
  country?: string;
  imageUrl: string;    // static JPEG/thumbnail
  videoUrl: string;    // HLS m3u8 | MP4 | YouTube URL | '' (fetched on demand)
  type: 'hls' | 'mp4' | 'youtube';
  source: 'nyc' | 'london' | 'openwebcamdb';
  slug?: string;       // OpenWebcamDB slug for on-demand stream URL fetch
  active: boolean;
}

export interface TrackedEntity {
  id: string;
  name: string;
  type: 'satellite' | 'flight' | 'earthquake' | 'cctv';
  lat?: number;
  lon?: number;
  altitude?: number;
  velocity?: number;
  heading?: number;
  extra?: Record<string, string | number>;
}

export interface ShaderParams {
  scanlineIntensity: number;
  pixelation: number;
  sensitivity: number;
  bloomBrightness: number;
}

export interface Landmark {
  key: string;
  name: string;
  lat: number;
  lon: number;
  alt: number;
  heading: number;
  pitch: number;
}

export interface City {
  name: string;
  landmarks: Landmark[];
}
