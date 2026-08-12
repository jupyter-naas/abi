import type { Dataset } from '@/lib/types';

/**
 * Scenario analysis engine. The dataset mixes four record kinds behind a `kind`
 * discriminator — the what-if cases, the per-driver sensitivities feeding the
 * tornado, a two-driver grid feeding the matrix, and the assumption values
 * behind each case.
 *
 * Records are monthly snapshots of the same forward-looking analysis, so this
 * reads the latest period in the selected window ("as of") rather than
 * aggregating across months — the same pattern the balance sheet uses.
 */

export type ScenarioKind = 'scenario' | 'driver' | 'sensitivity' | 'assumption';

export type DriverUnit = 'percent' | 'currency' | 'ratio';

type BaseRecord = {
  period: string;
  scenario: string;
  scenario_year: string;
  organization_slug?: string;
  entity_id?: string;
  kind: ScenarioKind;
};

export type ScenarioCaseRecord = BaseRecord & {
  kind: 'scenario';
  scenario_key: string;
  scenario_label: string;
  probability: number;
  is_base: boolean;
  description?: string;
  revenue: number;
  ebitda: number;
  cash: number;
  margin: number;
};

export type DriverRecord = BaseRecord & {
  kind: 'driver';
  driver_key: string;
  driver_label: string;
  unit: DriverUnit;
  base_value: number;
  low_value: number;
  high_value: number;
  low_impact: number;
  high_impact: number;
  hint?: string;
};

export type SensitivityRecord = BaseRecord & {
  kind: 'sensitivity';
  row_key: string;
  row_label: string;
  row_unit: DriverUnit;
  row_value: number;
  col_key: string;
  col_label: string;
  col_unit: DriverUnit;
  col_value: number;
  ebitda: number;
};

export type AssumptionRecord = BaseRecord & {
  kind: 'assumption';
  driver_key: string;
  driver_label: string;
  unit: DriverUnit;
  scenario_key: string;
  scenario_label: string;
  value: number;
  hint?: string;
};

export type ScenarioAnalysisRecord =
  | ScenarioCaseRecord
  | DriverRecord
  | SensitivityRecord
  | AssumptionRecord;

const KINDS = new Set<string>(['scenario', 'driver', 'sensitivity', 'assumption']);

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isScenarioAnalysisDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<ScenarioAnalysisRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function scenarioAnalysisRecords(
  dataset: Dataset | undefined,
): ScenarioAnalysisRecord[] {
  if (!isScenarioAnalysisDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) => typeof record.period === 'string' && KINDS.has(record.kind),
  );
}

/** "2026-12-31" → "Dec 2026". Falls back to the raw string when unparseable. */
export function formatPeriodLabel(period: string): string {
  const [year, month] = period.split('-');
  const index = Number(month) - 1;
  if (!year || index < 0 || index > 11) {
    return period;
  }
  return `${MONTH_ABBR[index]} ${year}`;
}

/** Drivers are rates unless declared otherwise; `ratio` reads as a multiple. */
export function formatDriverValue(value: number, unit: DriverUnit): string {
  if (unit === 'percent') {
    return new Intl.NumberFormat('fr-FR', {
      style: 'percent',
      maximumFractionDigits: 1,
      signDisplay: 'exceptZero',
    }).format(value);
  }
  if (unit === 'currency') {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  }
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export type ScenarioCase = {
  key: string;
  label: string;
  probability: number;
  isBase: boolean;
  description?: string;
  revenue: number;
  ebitda: number;
  cash: number;
  margin: number;
  /** Signed gaps to the base case. */
  revenueDelta: number;
  ebitdaDelta: number;
  cashDelta: number;
  marginDelta: number;
};

export type Driver = {
  key: string;
  label: string;
  unit: DriverUnit;
  baseValue: number;
  lowValue: number;
  highValue: number;
  lowImpact: number;
  highImpact: number;
  hint?: string;
  /** Total spread between the two impacts — drives the tornado ordering. */
  swing: number;
};

export type SensitivityGrid = {
  rowLabel: string;
  colLabel: string;
  rowUnit: DriverUnit;
  colUnit: DriverUnit;
  rowValues: number[];
  colValues: number[];
  /** `cells[rowIndex][colIndex]` — EBITDA at that driver combination. */
  cells: number[][];
};

export type AssumptionRow = {
  key: string;
  label: string;
  unit: DriverUnit;
  hint?: string;
  /** Value per scenario key. */
  values: Record<string, number>;
};

export type ScenarioKpis = {
  /** Probability-weighted expected outcome minus the base case. */
  revenueImpact: number;
  ebitdaImpact: number;
  cashImpact: number;
  marginImpact: number;
  /** Revenue needed to cover the current cost base (EBITDA = 0). */
  breakEven: number;
  /** Probability-weighted downside severity, 0–100. */
  riskScore: number;
};

export type WaterfallStep = {
  key: string;
  label: string;
  value: number;
  isTotal: boolean;
  start: number;
  end: number;
};

export type ScenarioAnalysisView = {
  asOf: string | null;
  asOfLabel: string;
  cases: ScenarioCase[];
  base: ScenarioCase | null;
  drivers: Driver[];
  sensitivity: SensitivityGrid | null;
  assumptions: AssumptionRow[];
  /** Scenario keys in display order, for the assumptions table columns. */
  scenarioColumns: { key: string; label: string }[];
  kpis: ScenarioKpis;
  /** Base EBITDA bridged through each driver's adverse impact. */
  waterfall: WaterfallStep[];
};

const EMPTY_KPIS: ScenarioKpis = {
  revenueImpact: 0,
  ebitdaImpact: 0,
  cashImpact: 0,
  marginImpact: 0,
  breakEven: 0,
  riskScore: 0,
};

/** Cases ordered best-to-worst by EBITDA for comparison charts. */
function byEbitdaDescending(a: ScenarioCase, b: ScenarioCase): number {
  return b.ebitda - a.ebitda;
}

export function buildScenarioAnalysis(
  records: ScenarioAnalysisRecord[],
): ScenarioAnalysisView {
  const periodIds = Array.from(new Set(records.map((r) => r.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;
  const snapshot = asOf ? records.filter((r) => r.period === asOf) : [];

  // --- scenarios.
  const caseRecords = snapshot.filter(
    (record): record is ScenarioCaseRecord => record.kind === 'scenario',
  );
  const baseRecord = caseRecords.find((record) => record.is_base) ?? caseRecords[0];

  const cases: ScenarioCase[] = caseRecords.map((record) => ({
    key: record.scenario_key,
    label: record.scenario_label,
    probability: record.probability,
    isBase: record.is_base,
    description: record.description,
    revenue: record.revenue,
    ebitda: record.ebitda,
    cash: record.cash,
    margin: record.margin,
    revenueDelta: record.revenue - (baseRecord?.revenue ?? 0),
    ebitdaDelta: record.ebitda - (baseRecord?.ebitda ?? 0),
    cashDelta: record.cash - (baseRecord?.cash ?? 0),
    marginDelta: record.margin - (baseRecord?.margin ?? 0),
  }));
  cases.sort(byEbitdaDescending);
  const base = cases.find((entry) => entry.isBase) ?? null;

  // --- drivers, ordered by total swing (tornado convention).
  const drivers: Driver[] = snapshot
    .filter((record): record is DriverRecord => record.kind === 'driver')
    .map((record) => ({
      key: record.driver_key,
      label: record.driver_label,
      unit: record.unit,
      baseValue: record.base_value,
      lowValue: record.low_value,
      highValue: record.high_value,
      lowImpact: record.low_impact,
      highImpact: record.high_impact,
      hint: record.hint,
      swing: Math.abs(record.high_impact - record.low_impact),
    }))
    .sort((a, b) => b.swing - a.swing);

  // --- sensitivity grid.
  const sensitivityRecords = snapshot.filter(
    (record): record is SensitivityRecord => record.kind === 'sensitivity',
  );
  let sensitivity: SensitivityGrid | null = null;
  if (sensitivityRecords.length > 0) {
    const rowValues = Array.from(
      new Set(sensitivityRecords.map((record) => record.row_value)),
    ).sort((a, b) => a - b);
    const colValues = Array.from(
      new Set(sensitivityRecords.map((record) => record.col_value)),
    ).sort((a, b) => a - b);
    const cells = rowValues.map((rowValue) =>
      colValues.map((colValue) => {
        const cell = sensitivityRecords.find(
          (record) => record.row_value === rowValue && record.col_value === colValue,
        );
        return cell?.ebitda ?? 0;
      }),
    );
    const sample = sensitivityRecords[0];
    sensitivity = {
      rowLabel: sample.row_label,
      colLabel: sample.col_label,
      rowUnit: sample.row_unit,
      colUnit: sample.col_unit,
      rowValues,
      colValues,
      cells,
    };
  }

  // --- assumptions, one row per driver and one column per scenario.
  const assumptionRecords = snapshot.filter(
    (record): record is AssumptionRecord => record.kind === 'assumption',
  );
  const assumptionKeys: string[] = [];
  for (const record of assumptionRecords) {
    if (!assumptionKeys.includes(record.driver_key)) {
      assumptionKeys.push(record.driver_key);
    }
  }
  const assumptions: AssumptionRow[] = assumptionKeys.map((key) => {
    const forDriver = assumptionRecords.filter((record) => record.driver_key === key);
    const values: Record<string, number> = {};
    for (const record of forDriver) {
      values[record.scenario_key] = record.value;
    }
    return {
      key,
      label: forDriver[0]?.driver_label ?? key,
      unit: forDriver[0]?.unit ?? 'percent',
      hint: forDriver[0]?.hint,
      values,
    };
  });

  const scenarioColumns = cases.map((entry) => ({ key: entry.key, label: entry.label }));

  // --- KPIs: probability-weighted expectation versus the base case.
  let kpis: ScenarioKpis = { ...EMPTY_KPIS };
  if (base && cases.length > 0) {
    const weight = cases.reduce((sum, entry) => sum + entry.probability, 0) || 1;
    const expected = (pick: (entry: ScenarioCase) => number) =>
      cases.reduce((sum, entry) => sum + entry.probability * pick(entry), 0) / weight;

    // All costs are held fixed across cases, so the revenue that exactly covers
    // them is the base cost base itself.
    const baseCosts = base.revenue - base.ebitda;

    // Severity of each downside case, weighted by how likely it is.
    const downside = cases.filter((entry) => entry.ebitda < base.ebitda);
    const riskRaw =
      base.ebitda !== 0
        ? downside.reduce(
            (sum, entry) =>
              sum +
              entry.probability * ((base.ebitda - entry.ebitda) / Math.abs(base.ebitda)),
            0,
          )
        : 0;

    kpis = {
      revenueImpact: expected((entry) => entry.revenue) - base.revenue,
      ebitdaImpact: expected((entry) => entry.ebitda) - base.ebitda,
      cashImpact: expected((entry) => entry.cash) - base.cash,
      marginImpact: expected((entry) => entry.margin) - base.margin,
      breakEven: baseCosts,
      riskScore: Math.max(0, Math.min(100, riskRaw * 100)),
    };
  }

  // --- waterfall: base EBITDA through each driver's adverse impact.
  // The end total is the sum of the steps by construction, so there is no plug.
  const waterfall: WaterfallStep[] = [];
  if (base && drivers.length > 0) {
    let running = base.ebitda;
    waterfall.push({
      key: 'base',
      label: 'Base EBITDA',
      value: base.ebitda,
      isTotal: true,
      start: 0,
      end: base.ebitda,
    });
    for (const driver of drivers) {
      const adverse = Math.min(driver.lowImpact, driver.highImpact);
      const start = running;
      running += adverse;
      waterfall.push({
        key: driver.key,
        label: driver.label,
        value: adverse,
        isTotal: false,
        start,
        end: running,
      });
    }
    waterfall.push({
      key: 'combined',
      label: 'All-adverse EBITDA',
      value: running,
      isTotal: true,
      start: 0,
      end: running,
    });
  }

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    cases,
    base,
    drivers,
    sensitivity,
    assumptions,
    scenarioColumns,
    kpis,
    waterfall,
  };
}
