import 'server-only';

import type { Dataset } from '@/lib/types';
import {
  aggregateUnpaidClientsDataset,
  isUnpaidClientsDataset,
} from '@/lib/data/unpaidClients';

export function aggregateConsolidationDataset(
  datasetKey: string,
  dataset: Dataset,
): Dataset {
  if (datasetKey === 'unpaid_clients' && isUnpaidClientsDataset(dataset)) {
    return aggregateUnpaidClientsDataset(dataset);
  }

  return dataset;
}

export function aggregateConsolidationDatasets(
  datasets: Record<string, Dataset>,
): Record<string, Dataset> {
  const aggregated: Record<string, Dataset> = {};

  for (const [key, dataset] of Object.entries(datasets)) {
    aggregated[key] = aggregateConsolidationDataset(key, dataset);
  }

  return aggregated;
}
