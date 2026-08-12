import 'server-only';

import type { CompanyConfig, EntityConfig, EntityId } from '@/lib/types';
import type { ScenarioOption, ScenarioSplit } from '@/lib/data/scenarios';
import { readJsonFile } from '@/lib/data/storage';

export type GlobalFilterDataset<T> = {
  schema_version: string;
  data_version: string;
  filter_type: string;
  records: T[];
};

export type ScenarioFilterRecord = ScenarioOption & {
  entity_id: EntityId;
  organization_slug?: string;
};

const GLOBAL_FILTER_ENTITIES_PATH = 'globals/filter-entities.json';
const GLOBAL_FILTER_SCENARIOS_PATH = 'globals/filter-scenarios.json';

export async function loadFilterEntities(): Promise<GlobalFilterDataset<EntityConfig> | null> {
  return readJsonFile<GlobalFilterDataset<EntityConfig>>(GLOBAL_FILTER_ENTITIES_PATH);
}

export async function loadFilterScenarios(): Promise<GlobalFilterDataset<ScenarioFilterRecord> | null> {
  return readJsonFile<GlobalFilterDataset<ScenarioFilterRecord>>(GLOBAL_FILTER_SCENARIOS_PATH);
}

/** @deprecated Use loadFilterEntities */
export const loadGlobalEntities = loadFilterEntities;

/** @deprecated Use loadFilterScenarios */
export const loadGlobalScenarios = loadFilterScenarios;

export function companiesForEntity(
  filterEntities: GlobalFilterDataset<EntityConfig> | null,
  entityId: EntityId,
): CompanyConfig[] | null {
  if (!filterEntities) {
    return null;
  }
  const record = filterEntities.records.find((entity) => entity.entity_id === entityId);
  return record?.companies ?? null;
}

export function scenariosForEntity(
  filterScenarios: GlobalFilterDataset<ScenarioFilterRecord> | null,
  entityId: EntityId,
  organizationSlug?: string | null,
): ScenarioOption[] {
  if (!filterScenarios) {
    return [];
  }

  const byKey = new Map<string, ScenarioOption>();
  for (const row of filterScenarios.records) {
    if (row.entity_id !== entityId) {
      continue;
    }
    if (
      organizationSlug &&
      row.organization_slug &&
      row.organization_slug !== organizationSlug
    ) {
      continue;
    }
    if (row.split !== 'date_month' && row.split !== 'date_year') {
      continue;
    }
    const key = `${row.split}:${row.id}`;
    byKey.set(key, {
      id: row.id,
      label: row.label,
      split: row.split as ScenarioSplit,
    });
  }

  return [...byKey.values()].sort((a, b) => {
    if (a.split !== b.split) {
      return a.split === 'date_month' ? -1 : 1;
    }
    return b.id.localeCompare(a.id);
  });
}
