import 'server-only';

import type { Dataset, EntityId, PageId } from '@/lib/types';
import { datasetKeyFromPath, recordEntityId } from '@/lib/data/filter';
import { loadEntityManifest, readJsonFile } from '@/lib/data/storage';

function normalizeDataset(entityId: EntityId, dataset: Dataset): Dataset {
  return {
    ...dataset,
    entity_id: dataset.entity_id ?? entityId,
    records: dataset.records.map((record) => {
      const memberEntityId = recordEntityId(record);
      if (memberEntityId) {
        return {
          ...record,
          entity_id: memberEntityId,
          organization_slug: record.organization_slug ?? memberEntityId,
        };
      }
      return record;
    }),
  };
}

function resolveDatasetPath(
  entityId: EntityId,
  manifestPath: string,
): string {
  if (manifestPath.startsWith('globals/')) {
    return manifestPath;
  }
  return `entities/${entityId}/${manifestPath}`;
}

export async function loadPageDatasets(
  entityId: EntityId,
  pageId: PageId,
): Promise<Record<string, Dataset>> {
  const manifest = await loadEntityManifest(entityId);
  if (!manifest) {
    return {};
  }

  const pagePaths =
    manifest.datasets.pages[pageId] ??
    // Legacy manifests keyed the unpaid-clients page as "invoices".
    (pageId === 'customer-invoices' ? manifest.datasets.pages.invoices : undefined) ??
    [];
  const datasets: Record<string, Dataset> = {};

  await Promise.all(
    pagePaths.map(async (manifestPath) => {
      const storagePath = resolveDatasetPath(entityId, manifestPath);
      const dataset = await readJsonFile<Dataset>(storagePath);
      if (dataset) {
        const key = datasetKeyFromPath(manifestPath);
        datasets[key] = normalizeDataset(entityId, dataset);
      }
    }),
  );

  const entityMetaPath = manifest.datasets.entity;
  if (entityMetaPath && !datasets.entity) {
    const storagePath = resolveDatasetPath(entityId, entityMetaPath);
    const entityDataset = await readJsonFile<Dataset>(storagePath);
    if (entityDataset) {
      datasets.entity = normalizeDataset(entityId, entityDataset);
    }
  }

  return datasets;
}

export async function getEntityDataVersion(
  entityId: EntityId,
): Promise<string | null> {
  const manifest = await loadEntityManifest(entityId);
  return manifest?.data_version ?? null;
}
