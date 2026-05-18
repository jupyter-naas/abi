/**
 * WSR BFO-aligned Domain Ontology — TypeScript Bindings
 *
 * This file is the canonical TypeScript mirror of:
 *   ontology/wsr.ttl       (class hierarchy)
 *   ontology/wsr-instances.ttl  (named individuals)
 *
 * Organisation follows the BFO 7-bucket pattern:
 *   1. Site              (WHERE)  — wsr:GeographicSite subclasses
 *   2. Material Entity   (WHO)    — wsr:Satellite, wsr:Aircraft, wsr:CCTVCameraUnit …
 *   3. GDC / ICE         (HOW WE KNOW) — wsr:InformationContentEntity subclasses
 *   4. Quality           (HOW IT IS)   — wsr:GeographicCoordinate …
 *   5. Role              (WHY — external) — wsr:SurveillanceSourceRole …
 *   6. Disposition       (WHY — internal) — wsr:StreamingDisposition …
 *   7. Process           (WHAT)   — wsr:GeospatialIntelligenceProcess subclasses
 *
 * RULE: All domain types in this app MUST be a subtype of one of these
 * seven base interfaces. If you add a new concept, determine its BFO
 * bucket first, then extend the correct base.
 */

// ─── Namespace constants ─────────────────────────────────────────────────────

export const WSR_NS = 'http://ontology.naas.ai/wsr/' as const;
export const WSRI_NS = 'http://ontology.naas.ai/wsr/instances/' as const;
export const BFO_NS = 'http://purl.obolibrary.org/obo/' as const;

// ─── Base BFO interfaces ──────────────────────────────────────────────────────

/**
 * Every named individual in the ontology carries a compact IRI and a
 * human-readable label.
 */
export interface OntologyEntity {
  readonly iri: string;
  readonly label: string;
}

/** BFO_0000029 — site */
export interface BFOSite extends OntologyEntity {
  readonly bfoType: 'Site';
}

/** BFO_0000040 — material entity */
export interface BFOMaterialEntity extends OntologyEntity {
  readonly bfoType: 'MaterialEntity';
}

/** BFO_0000031 — generically dependent continuant (information content entity) */
export interface BFOGDC extends OntologyEntity {
  readonly bfoType: 'GDC';
}

/** BFO_0000019 — quality */
export interface BFOQuality extends OntologyEntity {
  readonly bfoType: 'Quality';
}

/** BFO_0000023 — role */
export interface BFORole extends OntologyEntity {
  readonly bfoType: 'Role';
}

/** BFO_0000016 — disposition */
export interface BFODisposition extends OntologyEntity {
  readonly bfoType: 'Disposition';
}

/** BFO_0000015 — process */
export interface BFOProcess extends OntologyEntity {
  readonly bfoType: 'Process';
  /** BFO_0000066 occurs_in → Site IRI */
  readonly occursIn?: string;
  /** BFO_0000062 preceded_by → Process IRI */
  readonly precededBy?: string;
}

// ─── 1. SITES (WHERE) ────────────────────────────────────────────────────────

export type SiteType =
  | 'GeographicSite'
  | 'ConflictZone'
  | 'NuclearFacilitySite'
  | 'MilitaryBaseSite'
  | 'NavalOperatingArea'
  | 'UrbanSite'
  | 'AirspaceRegion'
  | 'OrbitalShell';

/**
 * wsr:GeographicSite and all subclasses.
 * Maps to ConflictEvent in the legacy API — but is now ontology-typed.
 */
export interface GeographicSite extends BFOSite {
  readonly siteType: SiteType;
  /** WGS84 decimal degrees */
  readonly lat: number;
  readonly lon: number;
  readonly country?: string;
  /** Assessed threat severity for conflict-relevant sites */
  readonly severity?: ThreatSeverityValue;
  readonly description?: string;
}

/** Threat severity values — wsr:ThreatSeverityLevel individuals */
export type ThreatSeverityValue = 'critical' | 'high' | 'medium' | 'low';

/** Canonical theater instance — wvi:MiddleEastTheater */
export const MIDDLE_EAST_THEATER: GeographicSite = {
  iri: `${WSRI_NS}MiddleEastTheater`,
  label: 'Middle East Theater of Operations',
  bfoType: 'Site',
  siteType: 'ConflictZone',
  lat: 30.0,
  lon: 40.0,
};

// ─── 2. MATERIAL ENTITIES (WHO) ──────────────────────────────────────────────

export type MaterialEntityType =
  | 'Satellite'
  | 'MilitaryAircraft'
  | 'CivilAircraft'
  | 'AerialRefuelingAircraft'
  | 'NavalVessel'
  | 'CCTVCameraUnit'
  | 'SeismographStation'
  | 'DataSourceEndpoint'
  | 'ComputeInfrastructure';

/**
 * wsr:Satellite — physical satellite object.
 * Linked to wsr:TLERecord (GDC) via BFO_0000101 is_carrier_of.
 */
export interface OntologySatellite extends BFOMaterialEntity {
  readonly materialType: 'Satellite';
  /** NORAD catalog number */
  readonly noradId: string;
  readonly name: string;
}

/**
 * wsr:Aircraft — tracked airborne material entity.
 * Bears wsr:ADSBTransponderDisposition.
 */
export interface OntologyAircraft extends BFOMaterialEntity {
  readonly materialType: 'MilitaryAircraft' | 'CivilAircraft' | 'AerialRefuelingAircraft';
  /** 24-bit Mode S transponder code */
  readonly icao24: string;
  readonly callsign?: string;
  /** Current position — quality instances */
  readonly position?: GeographicCoordinate;
  readonly altitude?: number;
  readonly velocity?: number;
  readonly heading?: number;
  readonly onGround?: boolean;
}

/**
 * wsr:CCTVCameraUnit — physical camera bearing wsr:StreamingDisposition.
 * Linked to wsr:VideoStream (GDC) via BFO_0000101 is_carrier_of.
 */
export interface OntologyCCTVCameraUnit extends BFOMaterialEntity {
  readonly materialType: 'CCTVCameraUnit';
  readonly id: string;
  readonly position: GeographicCoordinate;
  readonly city?: string;
  readonly country?: string;
  readonly videoUrl?: string;
  readonly imageUrl?: string;
  readonly streamType: 'hls' | 'youtube' | 'mp4' | 'mjpeg';
  readonly source: string;
  readonly active: boolean;
  readonly slug?: string;
}

/**
 * wsr:DataSourceEndpoint — server that produces ICEs.
 */
export interface OntologyDataSourceEndpoint extends BFOMaterialEntity {
  readonly materialType: 'DataSourceEndpoint';
  readonly sourceUrl: string;
  readonly cacheTTL: number;
}

// ─── 3. GENERICALLY DEPENDENT CONTINUANTS / ICEs (HOW WE KNOW) ──────────────

export type GDCType =
  | 'TLERecord'
  | 'AircraftPositionReport'
  | 'MilitaryAircraftReport'
  | 'EarthquakeEventRecord'
  | 'NewsArticle'
  | 'BreakingNewsArticle'
  | 'AlertNewsArticle'
  | 'ConflictSiteRecord'
  | 'VideoStream'
  | 'GeospatialVisualizationState'
  | 'RSSFeed';

/** Base information content entity */
export interface InformationContentEntity extends BFOGDC {
  readonly gdcType: GDCType;
  readonly sourceEndpointIri?: string;
  readonly fetchedAt?: number;
}

/**
 * wsr:TLERecord — orbital element set.
 * Generically depends on wvi:CelesTrakEndpoint.
 * Concretized by wvi:OrbitalPropagationProcess.
 */
export interface TLERecord extends InformationContentEntity {
  readonly gdcType: 'TLERecord';
  readonly name: string;
  readonly line1: string;
  readonly line2: string;
}

/**
 * wsr:AircraftPositionReport — ADS-B derived position.
 * Generically depends on OpenSky or airplanes.live endpoint.
 */
export interface AircraftPositionReport extends InformationContentEntity {
  readonly gdcType: 'AircraftPositionReport' | 'MilitaryAircraftReport';
  readonly icao24: string;
  readonly callsign?: string;
  readonly lat: number;
  readonly lon: number;
  readonly altitude: number;
  readonly velocity: number;
  readonly heading: number;
  readonly onGround: boolean;
  readonly isMilitary?: boolean;
}

/**
 * wsr:EarthquakeEventRecord — seismic event.
 * Generically depends on wvi:USGSEarthquakeEndpoint.
 */
export interface EarthquakeEventRecord extends InformationContentEntity {
  readonly gdcType: 'EarthquakeEventRecord';
  readonly id: string;
  readonly mag: number;
  readonly place: string;
  readonly lat: number;
  readonly lon: number;
  readonly depth: number;
  readonly time: number;
}

export type NewsSeverity = 'breaking' | 'alert' | 'update';

/**
 * wsr:NewsArticle — information content from a news organization.
 * Generically depends on BBC/AJ/Reuters RSS endpoint.
 * Bears wsr:NewsSeverityClass quality.
 */
export interface NewsArticle extends InformationContentEntity {
  readonly gdcType: 'NewsArticle' | 'BreakingNewsArticle' | 'AlertNewsArticle';
  readonly id: string;
  readonly title: string;
  readonly source: string;
  readonly url: string;
  readonly pubDate: number;
  readonly severity: NewsSeverity;
}

/**
 * wsr:ConflictSiteRecord — structured OSINT record for a conflict-relevant site.
 * Links an ICE to its corresponding GeographicSite instance.
 */
export interface ConflictSiteRecord extends InformationContentEntity {
  readonly gdcType: 'ConflictSiteRecord';
  readonly id: string;
  readonly name: string;
  readonly lat: number;
  readonly lon: number;
  readonly siteType: 'strike' | 'base' | 'nuclear' | 'naval' | 'zone' | 'capital';
  readonly country: string;
  readonly description: string;
  readonly severity: ThreatSeverityValue;
  /** IRI of the corresponding wsr:GeographicSite individual */
  readonly siteIri?: string;
}

/**
 * wsr:VideoStream — continuous video content from a physical camera.
 * Concretized by wsr:CCTVStreamingProcess.
 */
export interface VideoStream extends InformationContentEntity {
  readonly gdcType: 'VideoStream';
  readonly cameraId: string;
  readonly streamUrl: string;
  readonly streamType: 'hls' | 'youtube' | 'mp4' | 'mjpeg';
}

// ─── 4. QUALITIES (HOW IT IS) ────────────────────────────────────────────────

/** wsr:GeographicCoordinate — lat/lon quality pair */
export interface GeographicCoordinate extends BFOQuality {
  readonly bfoType: 'Quality';
  readonly lat: number;
  readonly lon: number;
}

/** wsr:ThreatSeverityLevel — composite theater threat assessment */
export type ThreatLevel = 'MONITORING' | 'ELEVATED' | 'HIGH' | 'IMMINENT';

export function computeThreatLevel(breakingCount: number): ThreatLevel {
  if (breakingCount >= 5) return 'IMMINENT';
  if (breakingCount >= 3) return 'HIGH';
  if (breakingCount >= 1) return 'ELEVATED';
  return 'MONITORING';
}

// ─── 5. ROLES (WHY — external) ───────────────────────────────────────────────

export type RoleType =
  | 'SurveillanceSourceRole'
  | 'IntelligenceSourceRole'
  | 'TrackingTargetRole'
  | 'TheaterActorRole'
  | 'AnalystRole';

export interface OntologyRole extends BFORole {
  readonly roleType: RoleType;
  /** IRI of the bearer (material entity) */
  readonly bearerIri: string;
}

// ─── 6. DISPOSITIONS (WHY — internal) ───────────────────────────────────────

export type DispositionType =
  | 'StreamingDisposition'
  | 'ADSBTransponderDisposition'
  | 'OrbitalPropagationDisposition'
  | 'SeismicSignatureDisposition'
  | 'NuclearProductionDisposition';

export interface OntologyDisposition extends BFODisposition {
  readonly dispositionType: DispositionType;
  /** IRI of the material entity that bears this disposition */
  readonly bearerIri: string;
}

// ─── 7. PROCESSES (WHAT) ─────────────────────────────────────────────────────

export type ProcessType =
  | 'SatelliteTrackingProcess'
  | 'OrbitalPropagationProcess'
  | 'FlightTrackingProcess'
  | 'TheaterAircraftMonitoringProcess'
  | 'EarthquakeMonitoringProcess'
  | 'NewsAggregationProcess'
  | 'ThreatAssessmentProcess'
  | 'CCTVStreamingProcess'
  | 'GlobeRenderingProcess'
  | 'GeocodingProcess'
  | 'ConflictZoneLoadingProcess'
  | 'DataCachingProcess';

/**
 * Runtime descriptor for a WSR process instance.
 * The refreshIntervalMs and cacheTTLMs mirror the wsr:hasRefreshInterval
 * and wsr:hasCacheTTL datatype properties in the TTL.
 */
export interface ProcessDescriptor extends BFOProcess {
  readonly processType: ProcessType;
  /** Polling interval in milliseconds (wsr:hasRefreshInterval × 1000) */
  readonly refreshIntervalMs?: number;
  /** Server-side cache TTL in milliseconds */
  readonly cacheTTLMs?: number;
  /** IRI of the site this process monitors */
  readonly theaterIri?: string;
  /** IRIs of data source endpoints this process uses (BFO_0000057 has_participant) */
  readonly sourceEndpoints: string[];
}

/**
 * Canonical process registry — single source of truth for all polling
 * intervals. Change here → change is reflected in both the code and
 * the ontology-level documentation.
 */
export const WSR_PROCESSES: Record<ProcessType, ProcessDescriptor> = {
  SatelliteTrackingProcess: {
    iri: `${WSRI_NS}SatelliteTrackingInstance`,
    label: 'Satellite Tracking Process',
    bfoType: 'Process',
    processType: 'SatelliteTrackingProcess',
    refreshIntervalMs: 3_000,
    cacheTTLMs: 3_600_000,
    sourceEndpoints: [`${WSRI_NS}CelesTrakEndpoint`],
  },
  OrbitalPropagationProcess: {
    iri: `${WSR_NS}OrbitalPropagationProcess`,
    label: 'SGP4 Orbital Propagation Subprocess',
    bfoType: 'Process',
    processType: 'OrbitalPropagationProcess',
    refreshIntervalMs: 3_000,
    cacheTTLMs: 0,
    sourceEndpoints: [],
  },
  FlightTrackingProcess: {
    iri: `${WSRI_NS}FlightTrackingInstance`,
    label: 'Civil Flight Tracking Process',
    bfoType: 'Process',
    processType: 'FlightTrackingProcess',
    refreshIntervalMs: 30_000,
    cacheTTLMs: 30_000,
    sourceEndpoints: [`${WSRI_NS}OpenSkyNetworkEndpoint`],
  },
  TheaterAircraftMonitoringProcess: {
    iri: `${WSRI_NS}TheaterAircraftMonitoringInstance`,
    label: 'Middle East Theater Aircraft Monitoring',
    bfoType: 'Process',
    processType: 'TheaterAircraftMonitoringProcess',
    refreshIntervalMs: 45_000,
    cacheTTLMs: 45_000,
    theaterIri: `${WSRI_NS}MiddleEastTheater`,
    sourceEndpoints: [`${WSRI_NS}AirplanesLiveEndpoint`],
  },
  EarthquakeMonitoringProcess: {
    iri: `${WSRI_NS}EarthquakeMonitoringInstance`,
    label: 'Global Earthquake Monitoring',
    bfoType: 'Process',
    processType: 'EarthquakeMonitoringProcess',
    refreshIntervalMs: 300_000,
    cacheTTLMs: 300_000,
    sourceEndpoints: [`${WSRI_NS}USGSEarthquakeEndpoint`],
  },
  NewsAggregationProcess: {
    iri: `${WSRI_NS}NewsAggregationInstance`,
    label: 'Theater News Aggregation',
    bfoType: 'Process',
    processType: 'NewsAggregationProcess',
    refreshIntervalMs: 180_000,
    cacheTTLMs: 180_000,
    theaterIri: `${WSRI_NS}MiddleEastTheater`,
    sourceEndpoints: [
      `${WSRI_NS}BBCMiddleEastRSS`,
      `${WSRI_NS}AlJazeeraRSS`,
      `${WSRI_NS}ReutersRSS`,
    ],
  },
  ThreatAssessmentProcess: {
    iri: `${WSRI_NS}ThreatAssessmentInstance`,
    label: 'Theater Threat Assessment',
    bfoType: 'Process',
    processType: 'ThreatAssessmentProcess',
    precededBy: `${WSRI_NS}NewsAggregationInstance`,
    theaterIri: `${WSRI_NS}MiddleEastTheater`,
    sourceEndpoints: [],
  },
  CCTVStreamingProcess: {
    iri: `${WSR_NS}CCTVStreamingProcess`,
    label: 'CCTV Video Stream Process',
    bfoType: 'Process',
    processType: 'CCTVStreamingProcess',
    cacheTTLMs: 300_000,
    sourceEndpoints: [],
  },
  GlobeRenderingProcess: {
    iri: `${WSRI_NS}GlobeRenderingInstance`,
    label: 'Cesium Globe Rendering Process',
    bfoType: 'Process',
    processType: 'GlobeRenderingProcess',
    refreshIntervalMs: 16,
    sourceEndpoints: [],
  },
  GeocodingProcess: {
    iri: `${WSR_NS}GeocodingProcess`,
    label: 'Nominatim Geocoding Process',
    bfoType: 'Process',
    processType: 'GeocodingProcess',
    sourceEndpoints: [`${WSRI_NS}NominatimEndpoint`],
  },
  ConflictZoneLoadingProcess: {
    iri: `${WSRI_NS}ConflictZoneLoadingInstance`,
    label: 'Conflict Zone Static Data Loading',
    bfoType: 'Process',
    processType: 'ConflictZoneLoadingProcess',
    theaterIri: `${WSRI_NS}MiddleEastTheater`,
    sourceEndpoints: [],
  },
  DataCachingProcess: {
    iri: `${WSR_NS}DataCachingProcess`,
    label: 'Server-Side API Response Caching',
    bfoType: 'Process',
    processType: 'DataCachingProcess',
    sourceEndpoints: [`${WSRI_NS}WSRNextJSServer`],
  },
};

// ─── Ontology-level IRI map for site instances ───────────────────────────────

/**
 * Maps the legacy `ConflictEvent.id` strings to their canonical
 * wvi: site IRIs. This is the bridge between old and new.
 */
export const CONFLICT_SITE_IRI_MAP: Record<string, string> = {
  'natanz':         `${WSRI_NS}NatanzEnrichmentComplex`,
  'fordow':         `${WSRI_NS}FordowFEP`,
  'isfahan':        `${WSRI_NS}IsfahanNuclearTechnologyCentre`,
  'arak':           `${WSRI_NS}ArakHeavyWaterReactor`,
  'bushehr':        `${WSRI_NS}BushehrNuclearPowerPlant`,
  'tehran':         `${WSRI_NS}TehranCapital`,
  'irgc':           `${WSRI_NS}IRGCAerospaceHQ`,
  'tel-aviv':       `${WSRI_NS}TelAvivIDF`,
  'dimona':         `${WSRI_NS}NegevNuclearResearchCentre`,
  'nevatim':        `${WSRI_NS}NevatimAirBase`,
  'haifa':          `${WSRI_NS}HaifaNavalBase`,
  'al-udeid':       `${WSRI_NS}AlUdeidAirBase`,
  'al-dhafra':      `${WSRI_NS}AlDhafraAirBase`,
  'persian-gulf-csg': `${WSRI_NS}PersianGulfCSGArea`,
  'hormuz':         `${WSRI_NS}StraitOfHormuz`,
  'beirut':         `${WSRI_NS}BeirutHezbollahZone`,
  'damascus':       `${WSRI_NS}DamascusCorridorZone`,
};
