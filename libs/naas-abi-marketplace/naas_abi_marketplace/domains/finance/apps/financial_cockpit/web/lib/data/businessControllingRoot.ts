import { join } from 'path';

const DEFAULT_FINANCE_DATA_ROOT = join(
  '..',
  '..',
  '..',
  '..',
  '..',
  'storage',
  'datastore',
  'business_controlling',
  'apps',
  'finance',
  'data',
);

export function getFinanceDataRoot(): string {
  return join(process.cwd(), process.env.DATA_LOCAL_ROOT ?? DEFAULT_FINANCE_DATA_ROOT);
}

/** Root of the business_controlling datastore (organizations + consolidations). */
export function getBusinessControllingRoot(): string {
  return join(getFinanceDataRoot(), '..', '..', '..');
}

export const ALL_ENTITIES_CONSOLIDATION = 'all_entities';
