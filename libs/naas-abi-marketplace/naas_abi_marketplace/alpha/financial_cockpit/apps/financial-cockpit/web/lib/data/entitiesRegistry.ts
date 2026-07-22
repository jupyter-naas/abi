import 'server-only';

import type { EntityConfig } from '@/lib/types';
import { readJsonFile } from '@/lib/data/storage';

// The entity registry is generated data, not app config: it lives in the
// datastore (local dir in dev, R2 in prod) and is loaded through the single
// ENV-switched data path like every other dataset.
export const GLOBAL_ENTITIES_REGISTRY_PATH = 'globals/entities.json';

export type EntitiesRegistry = {
  schema_version: string;
  data_version: string;
  entities: EntityConfig[];
};

export async function loadEntitiesRegistry(): Promise<EntityConfig[]> {
  const parsed = await readJsonFile<EntitiesRegistry>(GLOBAL_ENTITIES_REGISTRY_PATH);
  return parsed?.entities ?? [];
}
