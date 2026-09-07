import 'server-only';

import type { Dataset, EntityConfig } from '@/lib/types';
import type { ScenarioSplit } from '@/lib/data/scenarios';
import { isConsolidation } from '@/lib/config/loadConfig';
import { aggregateConsolidationDatasets } from '@/lib/data/aggregate';
import { applyRecordFiltersToDatasets } from '@/lib/data/filter';
import {
  isUnpaidClientsDataset,
  recomputeUnpaidView,
} from '@/lib/data/unpaidClients';

export type PageDatasetFilters = {
  siteId?: string | null;
  /** Organization entity_id (same as organization_slug in portal data). */
  organizationSlug?: string | null;
  /** Scenario id (YYYY-MM for months, YYYY for years). */
  scenarioId?: string | null;
  scenarioSplit?: ScenarioSplit | null;
};

export function preparePageDatasets(
  entity: EntityConfig,
  rawDatasets: Record<string, Dataset>,
  filters: PageDatasetFilters,
): Record<string, Dataset> {
  const organizationSlug = filters.organizationSlug ?? null;
  let datasets = applyRecordFiltersToDatasets(rawDatasets, {
    siteId: filters.siteId ?? null,
    organizationSlug,
    scenarioId: filters.scenarioId ?? null,
    scenarioSplit: filters.scenarioSplit ?? null,
  });

  if (isConsolidation(entity) && !organizationSlug) {
    datasets = aggregateConsolidationDatasets(datasets);
  } else if (datasets.unpaid_clients && isUnpaidClientsDataset(datasets.unpaid_clients)) {
    datasets = {
      ...datasets,
      unpaid_clients: recomputeUnpaidView(
        datasets.unpaid_clients,
        datasets.unpaid_clients.records,
      ),
    };
  }

  return datasets;
}
