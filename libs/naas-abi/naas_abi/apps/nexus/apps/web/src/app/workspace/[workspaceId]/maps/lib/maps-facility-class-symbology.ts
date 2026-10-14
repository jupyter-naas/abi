/** Lucide icon names for organization-facility `classLabel` legend rows. */

const CLASS_ICON: Record<string, string> = {
  'onshore wind': 'Wind',
  'offshore wind': 'Wind',
  solar: 'Sun',
  storage: 'Battery',
  'renewable project': 'Zap',
  nuclear: 'Atom',
  hydro: 'Droplets',
  'gas ccgt': 'Flame',
  biomass: 'Leaf',
  'pumped storage': 'Battery',
  agency: 'Building2',
};

function normalizeClassLabel(label: string): string {
  return label.trim().toLowerCase();
}

export function facilityClassIcon(classLabel: string | undefined): string | undefined {
  if (!classLabel?.trim()) return undefined;
  const key = normalizeClassLabel(classLabel);
  if (CLASS_ICON[key]) return CLASS_ICON[key];
  if (key.includes('wind')) return 'Wind';
  if (key.includes('solar')) return 'Sun';
  if (key.includes('nuclear')) return 'Atom';
  if (key.includes('hydro')) return 'Droplets';
  if (key.includes('biomass')) return 'Leaf';
  if (key.includes('storage')) return 'Battery';
  return 'MapPin';
}
