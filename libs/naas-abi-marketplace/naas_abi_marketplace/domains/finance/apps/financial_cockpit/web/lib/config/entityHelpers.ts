import type { EntityConfig } from '@/lib/types';

export { ALL_ENTITIES_ENTITY_ID, sortConsolidations, sortOrganizations } from '@/lib/entitySort';

export function isConsolidation(entity: EntityConfig): boolean {
  return (entity.entity_type ?? 'organization') === 'consolidation';
}

export function isOrganization(entity: EntityConfig): boolean {
  return !isConsolidation(entity);
}
