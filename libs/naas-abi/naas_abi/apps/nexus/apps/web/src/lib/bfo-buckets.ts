export interface BfoBucketDef {
  uri: string;
  type: string;
  label: string;
  description: string;
  color: string;
  border: string;
}

export const BFO_BUCKET_DEFS: BfoBucketDef[] = [
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000040', type: 'Material Entity', label: 'Who',         description: 'Objects, people, organizations', color: '#3b82f6', border: '#2563eb' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000015', type: 'Process',         label: 'What',        description: 'Events, activities, changes',    color: '#22c55e', border: '#16a34a' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000008', type: 'Temporal Region', label: 'When',        description: 'Time periods, instants',          color: '#a855f7', border: '#9333ea' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000029', type: 'Site',            label: 'Where',       description: 'Locations, places',               color: '#f97316', border: '#ea580c' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000019', type: 'Quality',         label: 'How it is',   description: 'Properties, attributes',          color: '#ec4899', border: '#db2777' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000017', type: 'Realizable',      label: 'Why',         description: 'Roles & dispositions',            color: '#eab308', border: '#ca8a04' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000031', type: 'GDC',             label: 'How we know', description: 'Documents, data, plans',          color: '#06b6d4', border: '#0891b2' },
  { uri: 'http://purl.obolibrary.org/obo/BFO_0000001', type: 'Entity',          label: 'Entity',      description: 'Entity',                         color: '#6b7280', border: '#4b5563' },
  { uri: '',                                            type: 'Unknown',         label: 'Unknown',     description: 'Unclassified or unresolved bucket', color: '#9ca3af', border: '#6b7280' },
];

export const BFO_BUCKET_BY_URI: Record<string, BfoBucketDef> = Object.fromEntries(
  BFO_BUCKET_DEFS.filter((d) => d.uri).map((d) => [d.uri, d])
);

export const BFO_BUCKET_BY_TYPE: Record<string, BfoBucketDef> = Object.fromEntries(
  BFO_BUCKET_DEFS.map((d) => [d.type, d])
);

export function getBfoBucket(uri: string | undefined): BfoBucketDef | null {
  if (!uri) return null;
  return BFO_BUCKET_BY_URI[uri] ?? null;
}
