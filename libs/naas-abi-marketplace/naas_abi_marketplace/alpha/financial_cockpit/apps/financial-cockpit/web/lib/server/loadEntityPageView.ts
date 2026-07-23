import 'server-only';

import type { EntityConfig, PageId } from '@/lib/types';
import type { ScenarioSplit } from '@/lib/data/scenarios';
import { preparePageDatasets } from '@/lib/data/preparePageDatasets';
import { loadPageDatasets, getEntityDataVersion } from '@/lib/data/datasets';

export type EntityPageView = {
  entity: EntityConfig;
  pageId: PageId;
  siteSlug: string | null;
  companySlug: string | null;
  datasets: Awaited<ReturnType<typeof loadPageDatasets>>;
  dataVersion: string | null;
};

export async function loadEntityPageView(options: {
  entity: EntityConfig;
  pageId: PageId;
  siteSlug?: string | null;
  siteId?: string | null;
  companySlug?: string | null;
  organizationSlug?: string | null;
  scenarioId?: string | null;
  scenarioSplit?: ScenarioSplit | null;
}): Promise<EntityPageView> {
  const {
    entity,
    pageId,
    siteSlug = null,
    siteId = null,
    companySlug = null,
    organizationSlug = null,
    scenarioId = null,
    scenarioSplit = null,
  } = options;

  const rawDatasets = await loadPageDatasets(entity.entity_id, pageId);
  const datasets = preparePageDatasets(entity, rawDatasets, {
    siteId,
    organizationSlug,
    scenarioId,
    scenarioSplit,
  });
  const dataVersion = await getEntityDataVersion(entity.entity_id);

  return {
    entity,
    pageId,
    siteSlug,
    companySlug,
    datasets,
    dataVersion,
  };
}
