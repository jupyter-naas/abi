import 'server-only';

import { readJsonFile } from '@/lib/data/storage';

/**
 * Administration settings datasets — how the *instance* is configured, as
 * opposed to what a perimeter earned. They are therefore global
 * (`globals/admin/<name>.json`), not per-entity, and read-only in the app:
 * `scripts/administration/settings.py` writes them, deriving the accounting
 * and organization ones from the general ledger and the cost-center roster so
 * the settings pages agree with the finance pages by construction.
 */
export type AdminSettingsName =
  | 'business_units'
  | 'cost_centers'
  | 'roles'
  | 'permissions'
  | 'chart_of_accounts'
  | 'fiscal_years'
  | 'accounting_periods'
  | 'journals'
  | 'approval_flows'
  | 'notifications'
  | 'validation_rules'
  | 'integrations_erp'
  | 'integrations_banking'
  | 'integrations_api'
  | 'imports_exports'
  | 'system_logs'
  | 'sync_history';

export type AdminSettingsRecord = Record<string, unknown>;

type AdminSettingsFile = {
  schema_version: string;
  data_version: string;
  records: AdminSettingsRecord[];
};

/** Records for a settings dataset; an empty list when the file is missing. */
export async function readAdminSettings(
  name: AdminSettingsName,
): Promise<AdminSettingsRecord[]> {
  const file = await readJsonFile<AdminSettingsFile>(`globals/admin/${name}.json`);
  return Array.isArray(file?.records) ? file.records : [];
}

/** Number of records whose `field` equals one of `values` (case-insensitive). */
export function countBy(
  records: AdminSettingsRecord[],
  field: string,
  values: string[],
): number {
  const wanted = new Set(values.map((value) => value.toLowerCase()));
  return records.filter((record) => {
    const value = record[field];
    return typeof value === 'string' && wanted.has(value.toLowerCase());
  }).length;
}

/** Sum of a numeric field across records; non-numeric values count as zero. */
export function sumBy(records: AdminSettingsRecord[], field: string): number {
  return records.reduce((total, record) => {
    const value = record[field];
    return total + (typeof value === 'number' && Number.isFinite(value) ? value : 0);
  }, 0);
}

/** Distinct non-empty string values of a field. */
export function distinctBy(records: AdminSettingsRecord[], field: string): number {
  const seen = new Set<string>();
  for (const record of records) {
    const value = record[field];
    if (typeof value === 'string' && value.trim() !== '') {
      seen.add(value);
    }
  }
  return seen.size;
}
