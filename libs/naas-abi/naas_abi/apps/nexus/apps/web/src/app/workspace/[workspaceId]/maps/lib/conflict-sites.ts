/**
 * Static OSINT conflict pins owned by Nexus Maps (20 sites).
 * Source basis: IAEA public records, US DoD public releases, OSINT.
 * Data may mirror older demo lists; this module does not import WSR.
 * No ACLED key required for v1.
 */

export type ConflictSeverity = 'critical' | 'high' | 'medium';

export interface ConflictSite {
  id: string;
  name: string;
  lat: number;
  lng: number;
  type: string;
  country: string;
  description: string;
  severity: ConflictSeverity;
}

export const CONFLICT_SITES: ConflictSite[] = [
  {
    id: 'natanz',
    name: 'Natanz Enrichment Complex',
    lat: 33.724,
    lng: 51.727,
    type: 'nuclear',
    country: 'Iran',
    description:
      'Primary uranium enrichment facility. Underground centrifuge halls. IAEA monitored.',
    severity: 'critical',
  },
  {
    id: 'fordow',
    name: 'Fordow Fuel Enrichment Plant',
    lat: 34.884,
    lng: 50.997,
    type: 'nuclear',
    country: 'Iran',
    description:
      'Deep underground enrichment site near Qom. Highly hardened, 80m below rock.',
    severity: 'critical',
  },
  {
    id: 'isfahan',
    name: 'Isfahan Nuclear Technology Centre',
    lat: 32.607,
    lng: 51.649,
    type: 'nuclear',
    country: 'Iran',
    description:
      'Uranium conversion facility (UCF). Produces UF6 feed for centrifuges.',
    severity: 'high',
  },
  {
    id: 'arak',
    name: 'Arak Heavy Water Reactor',
    lat: 34.32,
    lng: 49.166,
    type: 'nuclear',
    country: 'Iran',
    description:
      'IR-40 heavy water reactor site. Modified under JCPOA. Plutonium production capability.',
    severity: 'high',
  },
  {
    id: 'bushehr',
    name: 'Bushehr Nuclear Power Plant',
    lat: 28.829,
    lng: 50.888,
    type: 'nuclear',
    country: 'Iran',
    description:
      'Russian-built civilian nuclear power station on the Persian Gulf coast.',
    severity: 'medium',
  },
  {
    id: 'tehran',
    name: 'Tehran, Iranian Capital',
    lat: 35.689,
    lng: 51.389,
    type: 'capital',
    country: 'Iran',
    description:
      'Seat of the Supreme Leader and IRGC command. IRGC HQ located in NE Tehran.',
    severity: 'critical',
  },
  {
    id: 'irgc-aerospace',
    name: 'IRGC Aerospace Force HQ',
    lat: 35.75,
    lng: 51.45,
    type: 'base',
    country: 'Iran',
    description:
      'Commands Iranian ballistic missile and drone programs. Shaheed / Shahed UAVs.',
    severity: 'critical',
  },
  {
    id: 'tel-aviv',
    name: 'Tel Aviv / IDF HQ',
    lat: 32.085,
    lng: 34.782,
    type: 'capital',
    country: 'Israel',
    description:
      'Israeli military HQ (Kirya). Financial and population center. Iron Dome batteries active.',
    severity: 'critical',
  },
  {
    id: 'dimona',
    name: 'Negev Nuclear Research Centre (Dimona)',
    lat: 30.973,
    lng: 35.143,
    type: 'nuclear',
    country: 'Israel',
    description:
      'Undeclared Israeli nuclear weapons research facility. Not under IAEA safeguards.',
    severity: 'high',
  },
  {
    id: 'nevatim',
    name: 'Nevatim Air Base',
    lat: 31.208,
    lng: 35.012,
    type: 'base',
    country: 'Israel',
    description:
      'Home of IAF F-35I Adir squadrons. Primary long-range strike platform.',
    severity: 'high',
  },
  {
    id: 'ramat-david',
    name: 'Ramat David Air Base',
    lat: 32.665,
    lng: 35.18,
    type: 'base',
    country: 'Israel',
    description:
      'Northern IAF base. F-16I squadrons. Key role in northern theater operations.',
    severity: 'medium',
  },
  {
    id: 'haifa',
    name: 'Haifa, Naval Base & Industry',
    lat: 32.794,
    lng: 34.99,
    type: 'naval',
    country: 'Israel',
    description:
      'Israeli Navy HQ. Rafael Advanced Defense Systems nearby. Critical port infrastructure.',
    severity: 'high',
  },
  {
    id: 'udeid',
    name: 'Al Udeid Air Base (Qatar)',
    lat: 25.117,
    lng: 51.314,
    type: 'base',
    country: 'Qatar (US CENTCOM)',
    description:
      'Largest US air base in Middle East. CENTCOM forward HQ. B-52, KC-135 operations.',
    severity: 'high',
  },
  {
    id: 'dhafra',
    name: 'Al Dhafra Air Base (UAE)',
    lat: 24.248,
    lng: 54.548,
    type: 'base',
    country: 'UAE (US Air Force)',
    description:
      'F-35A, U-2 reconnaissance, KC-10 tankers. Key ISR and strike enabler.',
    severity: 'high',
  },
  {
    id: 'ali-al-salem',
    name: 'Ali Al Salem Air Base (Kuwait)',
    lat: 29.347,
    lng: 47.521,
    type: 'base',
    country: 'Kuwait (US)',
    description:
      'US Army and Air Force hub near Iraq border. Critical logistics node.',
    severity: 'medium',
  },
  {
    id: 'carrier-strike',
    name: 'Persian Gulf, Carrier Strike Group AO',
    lat: 26.5,
    lng: 56.2,
    type: 'naval',
    country: 'US Navy',
    description:
      'Approximate operating area for CSG. Strait of Hormuz chokepoint. Iranian IRGC fast-boat threat.',
    severity: 'critical',
  },
  {
    id: 'hormuz',
    name: 'Strait of Hormuz',
    lat: 26.594,
    lng: 56.451,
    type: 'zone',
    country: 'International Waters',
    description:
      '~20% of global oil transit. Iranian mining threat. IRGC naval patrol zone.',
    severity: 'critical',
  },
  {
    id: 'beirut',
    name: 'Beirut, Hezbollah Presence',
    lat: 33.888,
    lng: 35.495,
    type: 'zone',
    country: 'Lebanon',
    description:
      'Hezbollah political and military HQ in southern suburbs (Dahiyeh). Active front.',
    severity: 'high',
  },
  {
    id: 'damascus',
    name: 'Damascus, Syrian Regime Axis',
    lat: 33.51,
    lng: 36.291,
    type: 'zone',
    country: 'Syria',
    description:
      'IRGC and Hezbollah logistics corridor. Repeated IAF interdiction strikes.',
    severity: 'high',
  },
  {
    id: 'baghdad',
    name: 'Baghdad, Iraqi PMF Militia',
    lat: 33.338,
    lng: 44.394,
    type: 'zone',
    country: 'Iraq',
    description:
      'Iran-aligned Popular Mobilization Forces (PMF) HQ. Proxy activity against US interests.',
    severity: 'medium',
  },
];

export const CONFLICT_SEVERITY_COLOR: Record<ConflictSeverity, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
};
