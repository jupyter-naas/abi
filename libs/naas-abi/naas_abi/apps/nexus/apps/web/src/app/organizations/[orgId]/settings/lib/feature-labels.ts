/** Display names of the feature flag keys (api core/feature_flags.py KNOWN_FEATURE_KEYS). */
export const FEATURE_LABELS: Record<string, string> = {
  maps: 'Maps',
  chat: 'Chat',
  files: 'Files',
  agents: 'Agents',
  skills: 'Skills',
  apps: 'Apps',
  marketplace: 'Marketplace',
  search: 'Search',
  ontology: 'Ontology',
  graph: 'Graph',
  datasets: 'Datasets',
  settings: 'Settings',
  code: 'Code',
  slides: 'Slides',
  documents: 'Documents',
  sheets: 'Sheets',
  board: 'Board',
};

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] || feature;
}

export function sortFeaturesByName(features: string[]): string[] {
  return [...features].sort((a, b) =>
    featureLabel(a).localeCompare(featureLabel(b), undefined, { sensitivity: 'base' })
  );
}
