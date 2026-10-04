/**
 * Globe Engine — Public API
 *
 * Import from here, not from internal sub-paths.
 * Mirrors naas-abi-core's __init__.py module exports.
 */

// Ports (interfaces)
export type { IGlobeLayerPort, GlobeLayerConfiguration, GlobeEvent, GlobeEventType, GlobeEventHandler } from './ports/IGlobeLayerPort';
export type { IDataSourcePort, DataSourceResult } from './ports/IDataSourcePort';
export type { ICesiumContextPort, ICesiumContextAware } from './ports/ICesiumContextPort';

// Engine
export { GlobeEngine, createGlobeEngine } from './GlobeEngine';

// Base adapter
export { GlobeLayerBase } from './adapters/GlobeLayerBase';
export { DataSourceBase } from './ports/IDataSourcePort';

// Spatial layer adapters
export { BorderLayerAdapter } from './adapters/layers/BorderLayerAdapter';
export { CityLabelAdapter } from './adapters/layers/CityLabelAdapter';
export { ConflictZoneAdapter } from './adapters/layers/ConflictZoneAdapter';
export { CCTVLayerAdapter } from './adapters/layers/CCTVLayerAdapter';

// Real-time layer adapters
export { FlightLayerAdapter } from './adapters/layers/FlightLayerAdapter';
export { MilitaryLayerAdapter } from './adapters/layers/MilitaryLayerAdapter';
export { TheaterAircraftAdapter } from './adapters/layers/TheaterAircraftAdapter';
export { EarthquakeLayerAdapter } from './adapters/layers/EarthquakeLayerAdapter';

// Data source adapters
export { FlightDataSource, MilitaryDataSource, TheaterAircraftDataSource } from './adapters/data/FlightDataSource';
export { EarthquakeDataSource, CCTVDataSource, ConflictEventDataSource } from './adapters/data/SpatialDataSources';
