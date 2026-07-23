import type { Dataset } from '@/lib/types';

/**
 * P&L statement model.
 *
 * Pure functions only — turns the seeded `pnl/actuals.json` records, the
 * user-entered accounting adjustments and the budget rows into the ordered
 * statement lines (Ventes → … → Résultat net) rendered by `PnlSection`.
 *
 * Sign convention: amounts keep their accounting sign from the GL (sales
 * positive, charges negative), so every subtotal is a plain sum. Budgets are
 * entered as positive numbers and signed here according to their P&L line.
 */

// --------------------------------------------------------------------------
// Records
// --------------------------------------------------------------------------

export type PnlRecord = {
  source: string;
  company: string;
  organization_slug?: string;
  entity_id?: string;
  invoice_id: string;
  invoice_number: string;
  invoice_label: string;
  thirdparty: string;
  famille_2: string;
  categorie_2: string;
  categorie_3: string;
  plan_item_number: string;
  plan_item_label: string;
  date: string;
  /** YYYY-MM */
  scenario: string;
  /** YYYY */
  scenario_year: string;
  amount: number;
};

export function isPnlDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<PnlRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function pnlRecords(dataset: Dataset | undefined): PnlRecord[] {
  if (!isPnlDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) => typeof record.amount === 'number' && !Number.isNaN(record.amount),
  );
}

// --------------------------------------------------------------------------
// User-entered data (adjustments + budget) — shared with the API routes
// --------------------------------------------------------------------------

/** Manual accounting adjustment merged into the actuals. Amount is signed. */
export type PnlAdjustment = {
  id: string;
  /** Organization slug, or the consolidation entity_id for perimeter-level rows. */
  organization_slug: string;
  company: string;
  famille_2: string;
  categorie_2: string;
  categorie_3: string;
  thirdparty: string;
  label: string;
  /** Type d'écriture (free text). */
  entry_type: string;
  /** Action (free text). */
  action: string;
  /** Commentaires (free text). */
  comments: string;
  /** YYYY-MM */
  month: string;
  amount: number;
  user: string;
  date_edited: string;
};

/** Budget entered per famille / catégorie / tiers, one row per year. */
export type PnlBudgetRow = {
  id: string;
  organization_slug: string;
  famille_2: string;
  categorie_2: string;
  thirdparty: string;
  /** YYYY */
  year: string;
  /** 12 positive amounts, January → December. Sign is applied by famille. */
  months: number[];
  user: string;
  date_edited: string;
};

// --------------------------------------------------------------------------
// Buckets & classification
// --------------------------------------------------------------------------

export type PnlBucket =
  | 'ventes'
  | 'travaux'
  | 'exploitation'
  | 'corporate'
  | 'autres'
  | 'dotations'
  | 'charges_financieres'
  | 'produits_financiers'
  | 'impot';

const POSITIVE_BUCKETS: readonly PnlBucket[] = ['ventes', 'produits_financiers'];

/** Famille vocabulary offered in the adjustment / budget editors. */
export const PNL_FAMILLES: readonly { value: string; bucket: PnlBucket }[] = [
  { value: '2.Ventes', bucket: 'ventes' },
  { value: '2.Travaux', bucket: 'travaux' },
  { value: "2.Charges d'Exploitation", bucket: 'exploitation' },
  { value: '2.Charges Corporate', bucket: 'corporate' },
  { value: 'Dotations aux amortissements & provisions', bucket: 'dotations' },
  { value: 'Charges Financières', bucket: 'charges_financieres' },
  { value: 'Produits Financiers', bucket: 'produits_financiers' },
  { value: 'Impôt sur les Sociétés', bucket: 'impot' },
];

export function accentFold(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

const FAMILLE_BUCKET_BY_KEY = new Map<string, PnlBucket>(
  PNL_FAMILLES.map(({ value, bucket }) => [accentFold(value), bucket]),
);

/** 'CH CORPORATE / RH - Salaires' → 'rh - salaires' (accent-folded). */
function corporateCategoryKey(categorie2: string): string {
  const folded = accentFold(categorie2);
  return folded.replace(/^ch corporate\s*\/\s*/, '');
}

/**
 * "Calcul sur feuille" sub-groups of CHARGES CORPORATE, in display order.
 * Categories are matched on the accent-folded name without the
 * 'CH CORPORATE /' prefix; aliases cover spelling variants in the GL.
 */
export const CORPORATE_GROUPS: readonly { label: string; categories: string[] }[] = [
  {
    label: 'Charges du personnel',
    categories: [
      'rh - salaires',
      'rh - formations',
      'rh - medecine du travail',
      'rh - mutuelle & prevoyance',
      'rh - tickets restaurant',
      'rh - urssaf',
      'fiscalite - pas',
      'events - avantages rh',
      'events / avantages rh',
    ],
  },
  {
    label: 'Immobilier & Locaux',
    categories: ['loyer', 'locations & leasings'],
  },
  {
    label: 'Assurances',
    categories: ['assurance'],
  },
  {
    label: 'Finance & Honoraires',
    categories: [
      'finance & compta',
      'frais bancaires',
      'honoraires juridique & huissier',
      'honoraires rh',
      'management fees',
      'honoraires conseil',
    ],
  },
  {
    label: 'IT & Equipements',
    categories: [
      'ordinateurs & equipements',
      'logiciels & services web',
      'internet & telephonie',
    ],
  },
  {
    label: 'Marketing & R&D',
    categories: [
      'marketing',
      'frais de recherche et developpement',
      'frais de recherche & developpement',
    ],
  },
  {
    label: 'Frais generaux & Deplacements',
    categories: [
      'deplacements & stationnements',
      'deplacement & stationnement',
      'alimentaire',
      'fournitures, petits materiels & accessoires',
    ],
  },
  {
    label: 'Impots & Taxes',
    categories: ['fiscalite - cfe'],
  },
];

export const CORPORATE_FALLBACK_GROUP = 'Autres charges corporate';

const CORPORATE_GROUP_BY_CATEGORY = new Map<string, string>(
  CORPORATE_GROUPS.flatMap((group) =>
    group.categories.map((category) => [category, group.label] as const),
  ),
);

export function corporateGroupLabel(categorie2: string): string {
  return (
    CORPORATE_GROUP_BY_CATEGORY.get(corporateCategoryKey(categorie2)) ??
    CORPORATE_FALLBACK_GROUP
  );
}

function normalizedFamille(record: Pick<PnlRecord, 'famille_2'>): string {
  return accentFold(record.famille_2);
}

/** Assign a record (actual or adjustment) to exactly one P&L bucket. */
export function classifyRecord(record: PnlRecord): PnlBucket {
  const famille = normalizedFamille(record);
  const familleBucket = FAMILLE_BUCKET_BY_KEY.get(famille);

  if (record.source === 'Ajustement') {
    return familleBucket ?? 'autres';
  }
  if (record.source === 'Customers Invoices') {
    return 'ventes';
  }

  const plan = record.plan_item_number ?? '';
  const category = corporateCategoryKey(record.categorie_2 ?? '');

  if (plan.startsWith('68') || category.startsWith('dotations amortissements')) {
    return 'dotations';
  }
  if (
    plan.startsWith('66') ||
    famille === '2.charges financieres' ||
    category.startsWith('charges financieres')
  ) {
    return 'charges_financieres';
  }
  if (plan.startsWith('695') || plan.startsWith('698') || plan.startsWith('699')) {
    return 'impot';
  }
  if (plan.startsWith('76')) {
    return 'produits_financiers';
  }
  if (familleBucket && familleBucket !== 'ventes') {
    return familleBucket;
  }
  return 'autres';
}

export function budgetBucket(famille2: string): PnlBucket {
  return FAMILLE_BUCKET_BY_KEY.get(accentFold(famille2)) ?? 'autres';
}

/** Budgets are entered positive; sign them like the actuals of their line. */
export function signedBudgetAmount(bucket: PnlBucket, amount: number): number {
  const magnitude = Math.abs(amount);
  return POSITIVE_BUCKETS.includes(bucket) ? magnitude : -magnitude;
}

// --------------------------------------------------------------------------
// Periods
// --------------------------------------------------------------------------

export type PnlGranularity = 'year' | 'quarter' | 'month';

export const GRANULARITY_LABELS: Record<PnlGranularity, string> = {
  year: 'Année',
  quarter: 'Trimestre',
  month: 'Mois',
};

export type PnlPeriod = {
  id: string;
  label: string;
  /** YYYY-MM keys covered by this period. */
  months: string[];
  /** 1-based month indexes (within the scenario year) for budget lookups. */
  monthIndexes: number[];
  year: string;
};

const MONTH_LABELS = [
  'Janv',
  'Févr',
  'Mars',
  'Avr',
  'Mai',
  'Juin',
  'Juil',
  'Août',
  'Sept',
  'Oct',
  'Nov',
  'Déc',
];

function monthKey(year: string, monthIndex: number): string {
  return `${year}-${String(monthIndex).padStart(2, '0')}`;
}

/**
 * Columns of the statement for the active scenario:
 *  - month scenario (YYYY-MM): that single month;
 *  - year scenario: one column (year), four (quarters) or twelve (months);
 *  - no scenario ("all"): one column per year found in the data.
 */
export function buildPeriods(
  scenarioId: string | null,
  granularity: PnlGranularity,
  records: PnlRecord[],
  budgetRows: PnlBudgetRow[],
): PnlPeriod[] {
  const trimmed = scenarioId?.trim() ?? '';

  if (/^\d{4}-\d{2}$/.test(trimmed)) {
    const year = trimmed.slice(0, 4);
    const monthIndex = Number(trimmed.slice(5, 7));
    return [
      {
        id: trimmed,
        label: `${MONTH_LABELS[monthIndex - 1] ?? trimmed} ${year}`,
        months: [trimmed],
        monthIndexes: [monthIndex],
        year,
      },
    ];
  }

  if (/^\d{4}$/.test(trimmed)) {
    if (granularity === 'year') {
      return [
        {
          id: trimmed,
          label: trimmed,
          months: Array.from({ length: 12 }, (_, i) => monthKey(trimmed, i + 1)),
          monthIndexes: Array.from({ length: 12 }, (_, i) => i + 1),
          year: trimmed,
        },
      ];
    }
    if (granularity === 'quarter') {
      return [0, 1, 2, 3].map((quarter) => {
        const monthIndexes = [1, 2, 3].map((i) => quarter * 3 + i);
        return {
          id: `${trimmed}-T${quarter + 1}`,
          label: `T${quarter + 1} ${trimmed}`,
          months: monthIndexes.map((i) => monthKey(trimmed, i)),
          monthIndexes,
          year: trimmed,
        };
      });
    }
    return Array.from({ length: 12 }, (_, i) => ({
      id: monthKey(trimmed, i + 1),
      label: MONTH_LABELS[i],
      months: [monthKey(trimmed, i + 1)],
      monthIndexes: [i + 1],
      year: trimmed,
    }));
  }

  // "Tous les scénarios" — one column per year present in actuals or budget.
  const years = new Set<string>();
  for (const record of records) {
    if (record.scenario_year) {
      years.add(record.scenario_year);
    }
  }
  for (const row of budgetRows) {
    if (row.year) {
      years.add(row.year);
    }
  }
  return [...years].sort().map((year) => ({
    id: year,
    label: year,
    months: Array.from({ length: 12 }, (_, i) => monthKey(year, i + 1)),
    monthIndexes: Array.from({ length: 12 }, (_, i) => i + 1),
    year,
  }));
}

// --------------------------------------------------------------------------
// Statement
// --------------------------------------------------------------------------

export type PnlCell = { actual: number; budget: number };

export type PnlCells = { periods: PnlCell[]; total: PnlCell };

export type PnlCategoryRow = {
  key: string;
  label: string;
  cells: PnlCells;
  records: PnlRecord[];
};

export type PnlLine =
  | {
      kind: 'group';
      key: string;
      label: string;
      bucket: PnlBucket;
      /** Corporate sub-groups render indented under the CHARGES CORPORATE header. */
      nested: boolean;
      categories: PnlCategoryRow[];
      cells: PnlCells;
    }
  | { kind: 'total'; key: string; label: string; cells: PnlCells }
  | {
      kind: 'percent';
      key: string;
      label: string;
      /** Ratio (actual / ventes actual) per period + total; null when no base. */
      periods: (number | null)[];
      total: number | null;
    };

export type PnlStatement = {
  periods: PnlPeriod[];
  lines: PnlLine[];
  /** Whether budget columns carry meaningful values (disabled under Catégorie 3 filter). */
  budgetEnabled: boolean;
  kpis: {
    ventes: PnlCell;
    charges: PnlCell;
    margeBrute: PnlCell;
    margeBrutePct: number | null;
  };
};

export type PnlStatementOptions = {
  scenarioId: string | null;
  granularity: PnlGranularity;
  /** Selected Catégorie 3 values; empty = no filter. */
  categorie3Filter: ReadonlySet<string>;
  /** Perimeter slugs for adjustments / budget rows (orgs + conso entity id). */
  perimeterSlugs: ReadonlySet<string>;
};

export function adjustmentToRecord(adjustment: PnlAdjustment): PnlRecord {
  return {
    source: 'Ajustement',
    company: adjustment.company,
    organization_slug: adjustment.organization_slug,
    entity_id: adjustment.organization_slug,
    invoice_id: '',
    invoice_number: adjustment.id,
    invoice_label: adjustment.label || 'Ajustement comptable',
    thirdparty: adjustment.thirdparty,
    famille_2: adjustment.famille_2,
    categorie_2: adjustment.categorie_2,
    categorie_3: adjustment.categorie_3,
    plan_item_number: '',
    plan_item_label: 'Ajustement comptable',
    date: adjustment.month,
    scenario: adjustment.month,
    scenario_year: adjustment.month.slice(0, 4),
    amount: adjustment.amount,
  };
}

/** Adjustments visible on the current perimeter + scenario. */
export function filterAdjustments(
  adjustments: PnlAdjustment[],
  perimeterSlugs: ReadonlySet<string>,
  scenarioId: string | null,
): PnlAdjustment[] {
  const trimmed = scenarioId?.trim() ?? '';
  return adjustments.filter((adjustment) => {
    if (!perimeterSlugs.has(adjustment.organization_slug)) {
      return false;
    }
    if (!trimmed || trimmed === 'all') {
      return true;
    }
    return adjustment.month.startsWith(trimmed);
  });
}

export function filterBudgetRows(
  budgetRows: PnlBudgetRow[],
  perimeterSlugs: ReadonlySet<string>,
): PnlBudgetRow[] {
  return budgetRows.filter((row) => perimeterSlugs.has(row.organization_slug));
}

const UNCATEGORIZED = '(Non catégorisé)';

function emptyCell(): PnlCell {
  return { actual: 0, budget: 0 };
}

function emptyCells(periodCount: number): PnlCells {
  return {
    periods: Array.from({ length: periodCount }, emptyCell),
    total: emptyCell(),
  };
}

function addCells(target: PnlCells, source: PnlCells): void {
  source.periods.forEach((cell, index) => {
    target.periods[index].actual += cell.actual;
    target.periods[index].budget += cell.budget;
  });
  target.total.actual += source.total.actual;
  target.total.budget += source.total.budget;
}

type GroupAccumulator = {
  categories: Map<
    string,
    { label: string; cells: PnlCells; records: PnlRecord[] }
  >;
};

/** Groups keyed by bucket, with corporate split by sub-group label. */
type GroupKey = string;

function groupKeyFor(bucket: PnlBucket, categorie2: string): GroupKey {
  if (bucket === 'corporate') {
    return `corporate:${corporateGroupLabel(categorie2)}`;
  }
  return bucket;
}

export function buildPnlStatement(
  records: PnlRecord[],
  adjustments: PnlAdjustment[],
  budgetRows: PnlBudgetRow[],
  options: PnlStatementOptions,
): PnlStatement {
  const { scenarioId, granularity, categorie3Filter, perimeterSlugs } = options;
  const budgetEnabled = categorie3Filter.size === 0;

  const scopedBudget = budgetEnabled
    ? filterBudgetRows(budgetRows, perimeterSlugs)
    : [];
  const adjustmentRecords = filterAdjustments(
    adjustments,
    perimeterSlugs,
    scenarioId,
  ).map(adjustmentToRecord);

  let allRecords = [...records, ...adjustmentRecords];
  if (categorie3Filter.size > 0) {
    allRecords = allRecords.filter((record) =>
      categorie3Filter.has(record.categorie_3 || UNCATEGORIZED),
    );
  }

  const periods = buildPeriods(scenarioId, granularity, allRecords, scopedBudget);
  const periodIndexByMonth = new Map<string, number>();
  periods.forEach((period, index) => {
    for (const month of period.months) {
      periodIndexByMonth.set(month, index);
    }
  });

  const groups = new Map<GroupKey, GroupAccumulator>();

  function categoryAccumulator(groupKey: GroupKey, categorie2: string) {
    let group = groups.get(groupKey);
    if (!group) {
      group = { categories: new Map() };
      groups.set(groupKey, group);
    }
    const label = categorie2 || UNCATEGORIZED;
    let category = group.categories.get(label);
    if (!category) {
      category = { label, cells: emptyCells(periods.length), records: [] };
      group.categories.set(label, category);
    }
    return category;
  }

  for (const record of allRecords) {
    const periodIndex = periodIndexByMonth.get(record.scenario);
    if (periodIndex === undefined) {
      continue;
    }
    const bucket = classifyRecord(record);
    const category = categoryAccumulator(
      groupKeyFor(bucket, record.categorie_2),
      record.categorie_2,
    );
    category.cells.periods[periodIndex].actual += record.amount;
    category.cells.total.actual += record.amount;
    category.records.push(record);
  }

  for (const row of scopedBudget) {
    const bucket = budgetBucket(row.famille_2);
    const category = categoryAccumulator(
      groupKeyFor(bucket, row.categorie_2),
      row.categorie_2,
    );
    periods.forEach((period, periodIndex) => {
      if (period.year !== row.year) {
        return;
      }
      let amount = 0;
      for (const monthIndex of period.monthIndexes) {
        amount += row.months[monthIndex - 1] ?? 0;
      }
      const signed = signedBudgetAmount(bucket, amount);
      category.cells.periods[periodIndex].budget += signed;
      category.cells.total.budget += signed;
    });
  }

  // ---- assemble ordered lines ------------------------------------------- #

  const lines: PnlLine[] = [];
  const zero = () => emptyCells(periods.length);

  function groupLine(
    groupKey: GroupKey,
    label: string,
    bucket: PnlBucket,
    nested = false,
  ): Extract<PnlLine, { kind: 'group' }> | null {
    const group = groups.get(groupKey);
    if (!group || group.categories.size === 0) {
      return null;
    }
    const categories: PnlCategoryRow[] = [...group.categories.entries()]
      .map(([key, value]) => ({
        key: `${groupKey}:${key}`,
        label: value.label,
        cells: value.cells,
        records: value.records,
      }))
      .sort((a, b) => a.cells.total.actual - b.cells.total.actual);
    if (bucket === 'ventes') {
      categories.reverse();
    }
    const cells = zero();
    for (const category of categories) {
      addCells(cells, category.cells);
    }
    return { kind: 'group', key: groupKey, label, bucket, nested, categories, cells };
  }

  function pushGroup(
    groupKey: GroupKey,
    label: string,
    bucket: PnlBucket,
    nested = false,
  ): PnlCells {
    const line = groupLine(groupKey, label, bucket, nested);
    if (!line) {
      return zero();
    }
    lines.push(line);
    return line.cells;
  }

  function percentLine(key: string, label: string, cells: PnlCells, base: PnlCells) {
    lines.push({
      kind: 'percent',
      key,
      label,
      periods: cells.periods.map((cell, index) =>
        base.periods[index].actual ? cell.actual / base.periods[index].actual : null,
      ),
      total: base.total.actual ? cells.total.actual / base.total.actual : null,
    });
  }

  const ventes = pushGroup('ventes', 'Ventes', 'ventes');
  const travaux = pushGroup('travaux', 'Travaux', 'travaux');

  const margeBrute = zero();
  addCells(margeBrute, ventes);
  addCells(margeBrute, travaux);
  lines.push({ kind: 'total', key: 'marge_brute', label: 'MARGE BRUTE', cells: margeBrute });
  percentLine('marge_brute_pct', 'Marge Brute %', margeBrute, ventes);

  const exploitation = pushGroup(
    'exploitation',
    "Charges d'Exploitation",
    'exploitation',
  );

  // CHARGES CORPORATE header first, then its sub-groups (ordered per the
  // reporting sheet, fallback group last).
  const corporateKeys = [
    ...CORPORATE_GROUPS.map((group) => group.label),
    CORPORATE_FALLBACK_GROUP,
  ]
    .map((label) => ({ label, key: `corporate:${label}` }))
    .filter(({ key }) => groups.has(key));

  const corporate = zero();
  const corporateLines = corporateKeys
    .map(({ key, label }) => groupLine(key, label, 'corporate', true))
    .filter((line): line is Extract<PnlLine, { kind: 'group' }> => line !== null);
  for (const line of corporateLines) {
    addCells(corporate, line.cells);
  }
  if (corporateLines.length > 0) {
    lines.push({
      kind: 'total',
      key: 'charges_corporate',
      label: 'CHARGES CORPORATE',
      cells: corporate,
    });
    lines.push(...corporateLines);
  }

  const autres = pushGroup('autres', 'Autres charges', 'autres');

  const ebitda = zero();
  addCells(ebitda, margeBrute);
  addCells(ebitda, exploitation);
  addCells(ebitda, corporate);
  addCells(ebitda, autres);
  lines.push({ kind: 'total', key: 'ebitda', label: 'EBITDA', cells: ebitda });
  percentLine('ebitda_pct', 'EBITDA %', ebitda, ventes);

  const dotations = pushGroup(
    'dotations',
    'Dotations aux amortissements & provisions',
    'dotations',
  );

  const ebit = zero();
  addCells(ebit, ebitda);
  addCells(ebit, dotations);
  lines.push({
    kind: 'total',
    key: 'ebit',
    label: "EBIT / RÉSULTAT D'EXPLOITATION",
    cells: ebit,
  });
  percentLine('marge_operationnelle', 'Marge opérationnelle', ebit, ventes);

  const chargesFinancieres = pushGroup(
    'charges_financieres',
    'Charges Financières',
    'charges_financieres',
  );
  const produitsFinanciers = pushGroup(
    'produits_financiers',
    'Produits Financiers',
    'produits_financiers',
  );

  const resultatFinancier = zero();
  addCells(resultatFinancier, chargesFinancieres);
  addCells(resultatFinancier, produitsFinanciers);
  lines.push({
    kind: 'total',
    key: 'resultat_financier',
    label: 'RÉSULTAT FINANCIER',
    cells: resultatFinancier,
  });

  const rcai = zero();
  addCells(rcai, ebit);
  addCells(rcai, resultatFinancier);
  lines.push({
    kind: 'total',
    key: 'rcai',
    label: 'RÉSULTAT COURANT AVANT IMPÔT',
    cells: rcai,
  });

  const impot = pushGroup('impot', 'Impôt sur les Sociétés', 'impot');

  const resultatNet = zero();
  addCells(resultatNet, rcai);
  addCells(resultatNet, impot);
  lines.push({
    kind: 'total',
    key: 'resultat_net',
    label: 'RÉSULTAT NET',
    cells: resultatNet,
  });
  percentLine('marge_nette', 'Marge nette', resultatNet, ventes);

  // ---- KPIs -------------------------------------------------------------- #

  const charges = zero();
  addCells(charges, travaux);
  addCells(charges, exploitation);
  addCells(charges, corporate);
  addCells(charges, autres);

  return {
    periods,
    lines,
    budgetEnabled,
    kpis: {
      ventes: ventes.total,
      charges: charges.total,
      margeBrute: margeBrute.total,
      margeBrutePct: ventes.total.actual
        ? margeBrute.total.actual / ventes.total.actual
        : null,
    },
  };
}

// --------------------------------------------------------------------------
// Shared helpers for the sections
// --------------------------------------------------------------------------

/** Distinct, sorted Catégorie 3 values (empty mapped to a readable label). */
export function categorie3Options(records: PnlRecord[]): string[] {
  const values = new Set<string>();
  for (const record of records) {
    values.add(record.categorie_3 || UNCATEGORIZED);
  }
  return [...values].sort((a, b) => a.localeCompare(b, 'fr'));
}

export function categorie2Options(records: PnlRecord[]): string[] {
  const values = new Set<string>();
  for (const record of records) {
    if (record.categorie_2) {
      values.add(record.categorie_2);
    }
  }
  return [...values].sort((a, b) => a.localeCompare(b, 'fr'));
}

export function thirdpartyOptions(records: PnlRecord[]): string[] {
  const values = new Set<string>();
  for (const record of records) {
    if (record.thirdparty) {
      values.add(record.thirdparty);
    }
  }
  return [...values].sort((a, b) => a.localeCompare(b, 'fr'));
}

export const UNCATEGORIZED_LABEL = UNCATEGORIZED;
