import type { EntityConfig } from '@/lib/types';

export const ALL_ENTITIES_ENTITY_ID = 'all_entities';

const localeCompare = (a: string, b: string) =>
  a.localeCompare(b, 'fr', { sensitivity: 'base' });

export function sortOrganizations(entities: EntityConfig[]): EntityConfig[] {
  return [...entities].sort((a, b) => localeCompare(a.display_name, b.display_name));
}

export function sortConsolidations(entities: EntityConfig[]): EntityConfig[] {
  return [...entities].sort((a, b) => {
    if (a.entity_id === ALL_ENTITIES_ENTITY_ID) return -1;
    if (b.entity_id === ALL_ENTITIES_ENTITY_ID) return 1;
    return localeCompare(a.display_name, b.display_name);
  });
}
