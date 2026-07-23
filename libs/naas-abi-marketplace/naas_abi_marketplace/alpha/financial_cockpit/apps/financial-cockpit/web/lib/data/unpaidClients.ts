import type { Dataset } from '@/lib/types';
import type { ScenarioOption } from '@/lib/data/scenarios';

export type UnpaidSummary = {
  invoiced_amount_ttc: number;
  unpaid_amount_ttc: number;
  collected_amount_ttc: number;
  recovery_rate: number;
  unpaid_invoice_count: number;
  invoice_count: number;
};

export type AgingBucket = {
  bucket: string;
  label: string;
  amount: number;
  count: number;
};

export type UnpaidByCustomer = {
  client: string;
  site: string;
  entity_id?: string;
  organization_slug?: string;
  amount_unpaid_ttc: number;
  invoice_count: number;
};

export type RecoveryBarItem = {
  label: string;
  amount: number;
  count: number;
};

/** @deprecated Use RecoveryBarItem */
export type MiseEnDemeureBarItem = RecoveryBarItem;

export type UnpaidInvoiceRecord = {
  entity_id?: string;
  organization_slug?: string;
  company?: string;
  invoice_id: string;
  invoice_ref?: string;
  invoice_label?: string;
  client: string;
  site: string;
  /** Categorie_2 from the source CSV — displayed as “Catégorie analytique”. */
  categorie_2?: string | null;
  period?: string;
  date?: string;
  due_date?: string;
  scenario?: string;
  scenario_label?: string;
  scenario_year?: string;
  scenario_year_label?: string;
  status: string;
  status_label: string;
  recovery_action?: string;
  amount_ht: number;
  amount_ttc: number;
  remaining_amount_ttc: number;
  remaining_amount_ht: number;
  days_overdue: number;
  aging_bucket?: string | null;
  aging_label?: string | null;
  pdf_url?: string;
  is_unpaid?: boolean;
  pennylane_company_id?: number;
  pennylane_transactions_url?: string;
};

export const UNPAID_INVOICE_STATUSES = new Set(['late', 'partially_paid']);

/** Pennylane statuses dropped upstream — must match ``EXCLUDED_STATUS`` in dataset_builders.py. */
export const EXCLUDED_INVOICE_STATUSES = new Set([
  'archived',
  'incomplete',
  'cancelled',
  'draft',
]);

/** Unpaid = status late/partially_paid with remaining TTC > 0 (matches portal CSV rules). */
export function isUnpaidInvoiceRecord(record: UnpaidInvoiceRecord): boolean {
  if (record.is_unpaid === false) {
    return false;
  }
  const status = record.status?.trim().toLowerCase();
  if (!status || !UNPAID_INVOICE_STATUSES.has(status)) {
    return false;
  }
  return Number(record.remaining_amount_ttc ?? 0) > 0;
}

/** Detail table includes every late / partially_paid invoice, even with zero balance. */
export function isLateStatusInvoiceRecord(record: UnpaidInvoiceRecord): boolean {
  const status = record.status?.trim().toLowerCase();
  return Boolean(status && UNPAID_INVOICE_STATUSES.has(status));
}

export function filterUnpaidInvoiceRecords(
  records: UnpaidInvoiceRecord[],
): UnpaidInvoiceRecord[] {
  return records.filter(isUnpaidInvoiceRecord);
}

export function filterLateStatusInvoiceRecords(
  records: UnpaidInvoiceRecord[],
): UnpaidInvoiceRecord[] {
  return records.filter(isLateStatusInvoiceRecord);
}

/** Default detail-table scope: late and partially_paid only. */
export type InvoiceTableScope = 'late_status' | 'unpaid' | 'all';

export const DEFAULT_INVOICE_TABLE_SCOPE: InvoiceTableScope = 'late_status';

export function filterInvoiceTableRecords(
  records: UnpaidInvoiceRecord[],
  scope: InvoiceTableScope = DEFAULT_INVOICE_TABLE_SCOPE,
): UnpaidInvoiceRecord[] {
  switch (scope) {
    case 'unpaid':
      return filterUnpaidInvoiceRecords(records);
    case 'all':
      return records;
    case 'late_status':
    default:
      return filterLateStatusInvoiceRecords(records);
  }
}

export function filterTrackedInvoiceRecords(
  records: UnpaidInvoiceRecord[],
): UnpaidInvoiceRecord[] {
  return records.filter((record) => {
    const status = record.status?.trim().toLowerCase();
    return Boolean(status && !EXCLUDED_INVOICE_STATUSES.has(status));
  });
}

export function buildUnpaidSummary(records: UnpaidInvoiceRecord[]): UnpaidSummary {
  const tracked = filterTrackedInvoiceRecords(records);
  const unpaid = filterUnpaidInvoiceRecords(tracked);
  const invoiced_amount_ttc = tracked.reduce(
    (sum, row) => sum + Number(row.amount_ttc ?? 0),
    0,
  );
  const unpaid_amount_ttc = unpaid.reduce(
    (sum, row) => sum + Number(row.remaining_amount_ttc ?? 0),
    0,
  );
  const collected_amount_ttc = invoiced_amount_ttc - unpaid_amount_ttc;
  const recovery_rate = invoiced_amount_ttc
    ? collected_amount_ttc / invoiced_amount_ttc
    : 0;

  return {
    invoiced_amount_ttc: roundMoney(invoiced_amount_ttc),
    unpaid_amount_ttc: roundMoney(unpaid_amount_ttc),
    collected_amount_ttc: roundMoney(collected_amount_ttc),
    recovery_rate: Math.round(recovery_rate * 10000) / 10000,
    unpaid_invoice_count: unpaid.length,
    invoice_count: tracked.length,
  };
}

export type RecoveryAction =
  | ''
  | 'Relance Pennylane'
  | 'Relance Téléphonique'
  | 'Mise en demeure'
  | 'Arbitrage';

export type RecoveryActionKpis = {
  en_cours: { amount: number; count: number };
  relance_telephonique: { amount: number; count: number };
  mise_en_demeure: { amount: number; count: number };
  arbitrage: { amount: number; count: number };
};

export type RecoveryTone = 'success' | 'warning' | 'orange' | 'danger';

export const RECOVERY_ACTION_TABLE_LABELS = {
  relance_ok: 'Relance Pennylane',
  relance_telephonique: 'Relance Téléphonique',
  mise_en_demeure: 'Mise en demeure',
  arbitrage: 'Arbitrage',
} as const;

export const RECOVERY_ACTION_TONES: Record<string, RecoveryTone> = {
  [RECOVERY_ACTION_TABLE_LABELS.relance_ok]: 'success',
  [RECOVERY_ACTION_TABLE_LABELS.relance_telephonique]: 'warning',
  [RECOVERY_ACTION_TABLE_LABELS.mise_en_demeure]: 'orange',
  [RECOVERY_ACTION_TABLE_LABELS.arbitrage]: 'danger',
};

export function recoveryToneForLabel(label: string): RecoveryTone | null {
  return RECOVERY_ACTION_TONES[label] ?? null;
}

/** Default detail-table column filters (late + partially paid). */
export const DEFAULT_INVOICE_TABLE_COLUMN_FILTERS: Record<string, string> = {
  status_label: 'En retard|Partiellement payé',
};

export type RecoveryKpiFilterPreset =
  | 'all'
  | 'relance_telephonique'
  | 'mise_en_demeure'
  | 'arbitrage';

export function recoveryKpiTableView(preset: RecoveryKpiFilterPreset): {
  columnFilters: Record<string, string>;
  showAllRows: boolean;
} {
  switch (preset) {
    case 'all':
      return {
        columnFilters: DEFAULT_INVOICE_TABLE_COLUMN_FILTERS,
        showAllRows: true,
      };
    case 'relance_telephonique':
      return {
        columnFilters: {
          recovery_action_label: RECOVERY_ACTION_TABLE_LABELS.relance_telephonique,
        },
        showAllRows: false,
      };
    case 'mise_en_demeure':
      return {
        columnFilters: {
          recovery_action_label: RECOVERY_ACTION_TABLE_LABELS.mise_en_demeure,
        },
        showAllRows: false,
      };
    case 'arbitrage':
      return {
        columnFilters: {
          recovery_action_label: RECOVERY_ACTION_TABLE_LABELS.arbitrage,
        },
        showAllRows: false,
      };
  }
}

export const RECOVERY_ACTION_RULES: ReadonlyArray<{
  label: string;
  range: string;
  tone: RecoveryTone;
}> = [
  { label: 'Relance Pennylane', range: '1 à 13 jours de retard', tone: 'success' },
  { label: 'Relance téléphonique', range: '14 à 20 jours de retard', tone: 'warning' },
  { label: 'Mise en demeure', range: '21 à 29 jours de retard', tone: 'orange' },
  { label: 'Arbitrage', range: '30 jours de retard et plus', tone: 'danger' },
];

export function recoveryRuleHint(label: string): string {
  const rule = RECOVERY_ACTION_RULES.find((entry) => entry.label.startsWith(label));
  return rule ? `${rule.label} — ${rule.range}` : label;
}

export function recoveryRulesHint(): string {
  return RECOVERY_ACTION_RULES.map((rule) => `${rule.label} — ${rule.range}`).join('\n');
}

/** IF due date empty → ""; elif days≥30 → Arbitrage; elif days≥21 → Mise en demeure; elif days≥14 → Relance Téléphonique; elif days>0 → Relance Pennylane. */
export function computeRecoveryAction(
  dueDate: string | null | undefined,
  daysOverdue: number,
): RecoveryAction {
  if (!dueDate?.trim()) {
    return '';
  }
  if (daysOverdue >= 30) {
    return 'Arbitrage';
  }
  if (daysOverdue >= 21) {
    return 'Mise en demeure';
  }
  if (daysOverdue >= 14) {
    return 'Relance Téléphonique';
  }
  if (daysOverdue > 0) {
    return 'Relance Pennylane';
  }
  return '';
}

export function recoveryActionForRecord(record: UnpaidInvoiceRecord): RecoveryAction {
  if (record.recovery_action !== undefined) {
    return record.recovery_action as RecoveryAction;
  }
  return computeRecoveryAction(record.due_date, record.days_overdue);
}

export function aggregateRecoveryActionKpis(
  records: UnpaidInvoiceRecord[],
): RecoveryActionKpis {
  const unpaid = filterUnpaidInvoiceRecords(records);
  const kpis: RecoveryActionKpis = {
    en_cours: { amount: 0, count: 0 },
    relance_telephonique: { amount: 0, count: 0 },
    mise_en_demeure: { amount: 0, count: 0 },
    arbitrage: { amount: 0, count: 0 },
  };

  for (const row of unpaid) {
    const amount = Number(row.remaining_amount_ttc ?? 0);
    kpis.en_cours.amount += amount;
    kpis.en_cours.count += 1;

    const action = recoveryActionForRecord(row);
    if (action === 'Relance Téléphonique') {
      kpis.relance_telephonique.amount += amount;
      kpis.relance_telephonique.count += 1;
    } else if (action === 'Mise en demeure') {
      kpis.mise_en_demeure.amount += amount;
      kpis.mise_en_demeure.count += 1;
    } else if (action === 'Arbitrage') {
      kpis.arbitrage.amount += amount;
      kpis.arbitrage.count += 1;
    }
  }

  kpis.en_cours.amount = roundMoney(kpis.en_cours.amount);
  kpis.relance_telephonique.amount = roundMoney(kpis.relance_telephonique.amount);
  kpis.mise_en_demeure.amount = roundMoney(kpis.mise_en_demeure.amount);
  kpis.arbitrage.amount = roundMoney(kpis.arbitrage.amount);

  return kpis;
}

function roundMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

export function buildRecoveryCharts(records: UnpaidInvoiceRecord[]): {
  mise_en_demeure_by_client: RecoveryBarItem[];
  arbitrage_by_client: RecoveryBarItem[];
} {
  const aggregate = (
    rows: UnpaidInvoiceRecord[],
    pickLabel: (row: UnpaidInvoiceRecord) => string,
  ) => {
    const totals = new Map<string, { amount: number; count: number }>();
    for (const row of rows) {
      const label = pickLabel(row) || '—';
      const current = totals.get(label) ?? { amount: 0, count: 0 };
      current.amount += Number(row.remaining_amount_ttc ?? 0);
      current.count += 1;
      totals.set(label, current);
    }

    return Array.from(totals.entries())
      .map(([label, stats]) => ({
        label,
        amount: roundMoney(stats.amount),
        count: stats.count,
      }))
      .sort((a, b) => b.amount - a.amount || a.label.localeCompare(b.label, 'fr'));
  };

  const demeure = filterUnpaidInvoiceRecords(records).filter(
    (row) => recoveryActionForRecord(row) === 'Mise en demeure',
  );
  const arbitrage = filterUnpaidInvoiceRecords(records).filter(
    (row) => recoveryActionForRecord(row) === 'Arbitrage',
  );

  return {
    mise_en_demeure_by_client: aggregate(demeure, (row) => row.client),
    arbitrage_by_client: aggregate(arbitrage, (row) => row.client),
  };
}

/** @deprecated Use buildRecoveryCharts */
export function buildMiseEnDemeureCharts(records: UnpaidInvoiceRecord[]): {
  mise_en_demeure_by_client: RecoveryBarItem[];
  mise_en_demeure_by_site: RecoveryBarItem[];
} {
  const charts = buildRecoveryCharts(records);
  return {
    mise_en_demeure_by_client: charts.mise_en_demeure_by_client,
    mise_en_demeure_by_site: [],
  };
}

export function resolveRecoveryCharts(
  dataset: UnpaidClientsDataset,
  records: UnpaidInvoiceRecord[],
): {
  mise_en_demeure_by_client: RecoveryBarItem[];
  arbitrage_by_client: RecoveryBarItem[];
} {
  if (
    dataset.mise_en_demeure_by_client !== undefined &&
    dataset.arbitrage_by_client !== undefined &&
    records === dataset.records
  ) {
    return {
      mise_en_demeure_by_client: dataset.mise_en_demeure_by_client,
      arbitrage_by_client: dataset.arbitrage_by_client,
    };
  }
  return buildRecoveryCharts(records);
}

/** @deprecated Use resolveRecoveryCharts */
export function resolveMiseEnDemeureCharts(
  dataset: UnpaidClientsDataset,
  records: UnpaidInvoiceRecord[],
): {
  mise_en_demeure_by_client: RecoveryBarItem[];
  mise_en_demeure_by_site: RecoveryBarItem[];
} {
  const charts = resolveRecoveryCharts(dataset, records);
  return {
    mise_en_demeure_by_client: charts.mise_en_demeure_by_client,
    mise_en_demeure_by_site: dataset.mise_en_demeure_by_site ?? [],
  };
}

export type UnpaidClientsDataset = Dataset<UnpaidInvoiceRecord> & {
  summary: UnpaidSummary;
  aging_buckets: AgingBucket[];
  by_customer: UnpaidByCustomer[];
  scenarios?: ScenarioOption[];
  mise_en_demeure_by_client?: RecoveryBarItem[];
  arbitrage_by_client?: RecoveryBarItem[];
  /** @deprecated Replaced by arbitrage_by_client */
  mise_en_demeure_by_site?: RecoveryBarItem[];
};

export function isUnpaidClientsDataset(
  dataset: Dataset | undefined,
): dataset is UnpaidClientsDataset {
  return (
    dataset !== undefined &&
    'summary' in dataset &&
    'aging_buckets' in dataset &&
    'by_customer' in dataset
  );
}

const AGING_ORDER = ['0-30', '30-60', '60-90', '90+'];

export function aggregateUnpaidClientsDataset(
  dataset: UnpaidClientsDataset,
): UnpaidClientsDataset {
  const trackedRecords = filterTrackedInvoiceRecords(dataset.records);
  const unpaidRecords = filterUnpaidInvoiceRecords(trackedRecords);
  const summary = buildUnpaidSummary(trackedRecords);

  const agingMap = new Map<string, AgingBucket>();
  for (const bucket of dataset.aging_buckets) {
    agingMap.set(bucket.bucket, { ...bucket, amount: 0, count: 0 });
  }
  for (const row of unpaidRecords) {
    const bucketId = row.aging_bucket ?? '0-30';
    const current = agingMap.get(bucketId) ?? {
      bucket: bucketId,
      label: row.aging_label ?? bucketId,
      amount: 0,
      count: 0,
    };
    current.amount += Number(row.remaining_amount_ttc ?? 0);
    current.count += 1;
    agingMap.set(bucketId, current);
  }
  const aging_buckets = AGING_ORDER.map(
    (bucket) =>
      agingMap.get(bucket) ?? {
        bucket,
        label: bucket,
        amount: 0,
        count: 0,
      },
  );

  const customerMap = new Map<string, UnpaidByCustomer>();
  for (const row of unpaidRecords) {
    const key = `${row.client}\0${row.site}`;
    const current = customerMap.get(key) ?? {
      client: row.client,
      site: row.site,
      entity_id: row.entity_id ?? row.organization_slug,
      organization_slug: row.organization_slug ?? row.entity_id,
      amount_unpaid_ttc: 0,
      invoice_count: 0,
    };
    current.amount_unpaid_ttc += Number(row.remaining_amount_ttc ?? 0);
    current.invoice_count += 1;
    customerMap.set(key, current);
  }
  const by_customer = Array.from(customerMap.values()).sort(
    (a, b) => b.amount_unpaid_ttc - a.amount_unpaid_ttc,
  );

  const { mise_en_demeure_by_client, arbitrage_by_client } =
    buildRecoveryCharts(unpaidRecords);

  return {
    ...dataset,
    scenarios: dataset.scenarios,
    summary,
    aging_buckets,
    by_customer,
    mise_en_demeure_by_client,
    arbitrage_by_client,
    records: trackedRecords,
  };
}

export function recomputeUnpaidView(
  dataset: UnpaidClientsDataset,
  records: UnpaidInvoiceRecord[],
): UnpaidClientsDataset {
  return aggregateUnpaidClientsDataset({ ...dataset, records });
}
