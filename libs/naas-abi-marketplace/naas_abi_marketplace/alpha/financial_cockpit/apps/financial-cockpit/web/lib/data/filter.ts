import 'server-only';

import type { Dataset, EntityId } from '@/lib/types';

export function datasetKeyFromPath(relativePath: string): string {
  const filename = relativePath.split('/').pop() ?? relativePath;
  return filename.replace(/\.json$/, '');
}

export function recordEntityId(record: Record<string, unknown>): string | undefined {
  const entityId = record.entity_id;
  if (typeof entityId === 'string' && entityId.trim()) {
    return entityId;
  }
  const organizationSlug = record.organization_slug;
  if (typeof organizationSlug === 'string' && organizationSlug.trim()) {
    return organizationSlug;
  }
  return undefined;
}

export function filterBySite<T extends Record<string, unknown>>(
  records: T[],
  siteId: string | null | undefined,
): T[] {
  if (!siteId) {
    return records;
  }
  return records.filter((record) => record.site_id === siteId);
}

export function filterByMemberEntity<T extends Record<string, unknown>>(
  records: T[],
  memberEntityId: EntityId | null | undefined,
): T[] {
  if (!memberEntityId) {
    return records;
  }
  return records.filter((record) => recordEntityId(record) === memberEntityId);
}

/** @deprecated Use filterByMemberEntity */
export function filterByOrganization<T extends Record<string, unknown>>(
  records: T[],
  organizationSlug: string | null | undefined,
): T[] {
  return filterByMemberEntity(records, organizationSlug);
}

export function filterByScenario<T extends Record<string, unknown>>(
  records: T[],
  scenarioId: string | null | undefined,
  scenarioSplit?: 'date_month' | 'date_year' | null,
): T[] {
  if (!scenarioId) {
    return records;
  }
  if (scenarioSplit === 'date_year') {
    return records.filter((record) => String(record.scenario_year ?? '') === scenarioId);
  }
  return records.filter((record) => String(record.scenario ?? '') === scenarioId);
}

export function applyRecordFiltersToDatasets(
  datasets: Record<string, Dataset>,
  filters: {
    siteId?: string | null;
    organizationSlug?: string | null;
    scenarioId?: string | null;
    scenarioSplit?: 'date_month' | 'date_year' | null;
  },
): Record<string, Dataset> {
  const { siteId, organizationSlug, scenarioId, scenarioSplit } = filters;
  if (!siteId && !organizationSlug && !scenarioId) {
    return datasets;
  }

  const filtered: Record<string, Dataset> = {};
  for (const [key, dataset] of Object.entries(datasets)) {
    let records = dataset.records;
    if (siteId) {
      records = filterBySite(records, siteId);
    }
    if (organizationSlug) {
      records = filterByMemberEntity(records, organizationSlug);
    }
    if (scenarioId) {
      records = filterByScenario(records, scenarioId, scenarioSplit);
    }
    filtered[key] = {
      ...dataset,
      records,
    };
  }
  return filtered;
}

/** @deprecated Use applyRecordFiltersToDatasets */
export function applySiteFilterToDatasets(
  datasets: Record<string, Dataset>,
  siteId: string | null | undefined,
): Record<string, Dataset> {
  return applyRecordFiltersToDatasets(datasets, { siteId });
}
