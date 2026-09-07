import type { Dataset } from '@/lib/types';

/**
 * Financial close engine. Three record kinds share the dataset behind a `kind`
 * discriminator:
 *
 * - `task`  — one checklist task for one month.
 * - `issue` — one issue raised during that month's close.
 * - `memo`  — per-period aggregates: `close_duration_days`,
 *   `planned_duration_days`, `open_period`.
 *
 * A close is a **per-month exercise**, so the checklist, the progress bars and
 * every readiness KPI are read at the **as-of** period — the last month in the
 * window. Summing twelve checklists would answer no question anyone asks.
 *
 * Two figures deliberately span the whole window instead, because they only
 * mean something over a history: `closeDuration` (the mean business day the
 * last task landed, across the months that actually closed) and the issue
 * distribution.
 */

export type CloseRecord = {
  period: string; // period-end ISO date
  scenario: string; // YYYY-MM
  scenario_year: string; // YYYY
  organization_slug?: string;
  entity_id?: string;
  kind: 'task' | 'issue' | 'memo';
  /** `memo` rows only. */
  metric?: string;
  metric_label?: string;
  task_ref: string;
  task: string;
  task_label: string;
  area: string;
  area_label: string;
  owner: string;
  planned_start_day: number;
  planned_end_day: number;
  planned_start_date: string;
  planned_end_date: string;
  actual_start_date: string;
  actual_end_date: string;
  actual_end_day: number;
  status: string;
  status_label: string;
  is_done: boolean;
  is_late: boolean;
  days_late: number;
  is_validated: boolean;
  validator: string;
  severity: string;
  severity_label: string;
  title: string;
  raised_date: string;
  resolved_date: string;
  is_resolved: boolean;
  amount: number;
};

export type CloseStatusKey = 'done' | 'in_progress' | 'blocked' | 'not_started';

/** Task states, in the order the page reports them. */
export const CLOSE_STATUSES: { key: CloseStatusKey; label: string }[] = [
  { key: 'done', label: 'Done' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'not_started', label: 'Not started' },
];

/** Severities, worst first. */
export const SEVERITIES: { key: string; label: string }[] = [
  { key: 'high', label: 'High' },
  { key: 'medium', label: 'Medium' },
  { key: 'low', label: 'Low' },
];

const MONTH_ABBR = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function isCloseDataset(
  dataset: Dataset | undefined,
): dataset is Dataset<CloseRecord> {
  return Boolean(dataset && Array.isArray(dataset.records));
}

export function closeRecords(dataset: Dataset | undefined): CloseRecord[] {
  if (!isCloseDataset(dataset)) {
    return [];
  }
  return dataset.records.filter(
    (record) =>
      typeof record.period === 'string' &&
      typeof record.amount === 'number' &&
      !Number.isNaN(record.amount) &&
      (record.kind === 'task' || record.kind === 'issue' || record.kind === 'memo'),
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

export type AreaProgress = {
  key: string;
  label: string;
  total: number;
  done: number;
  running: number;
  blocked: number;
  notStarted: number;
  /** Share of the area's tasks that are done. */
  completion: number;
};

export type StatusGroup = {
  key: CloseStatusKey;
  label: string;
  count: number;
  share: number;
};

export type IssueGroup = {
  key: string;
  label: string;
  /** Issues raised in the area across the window. */
  count: number;
  open: number;
  high: number;
};

export type CloseDurationPoint = {
  period: string;
  label: string;
  /** Business day the last task landed. `null` while the month is not closed. */
  actual: number | null;
  planned: number;
};

export type CloseKpis = {
  /** Share of the as-of close's tasks that are done. */
  completion: number;
  taskCount: number;
  doneTasks: number;
  remainingTasks: number;
  lateTasks: number;
  blockedTasks: number;
  validatedTasks: number;
  /** Share of completed tasks a reviewer signed off. */
  validationRate: number | null;
  openIssues: number;
  highIssues: number;
  issueCount: number;
  /** Mean business day the close landed, across months that closed. */
  closeDuration: number | null;
  plannedDuration: number;
};

export type CloseView = {
  asOf: string | null;
  asOfLabel: string;
  /** The as-of month's books are still open — its close is what is on screen. */
  isOpen: boolean;
  /**
   * Business day the running close has reached, inferred from the last task
   * signed off. `null` once the month is closed (nothing is "now" any more) or
   * before the close has started.
   */
  progressDay: number | null;
  kpis: CloseKpis;
  /** The as-of month's checklist, in plan order. */
  tasks: CloseRecord[];
  areas: AreaProgress[];
  statuses: StatusGroup[];
  /** Issues raised across the window, most recent first. */
  issues: CloseRecord[];
  issueAreas: IssueGroup[];
  durations: CloseDurationPoint[];
};

const EMPTY_KPIS: CloseKpis = {
  completion: 0,
  taskCount: 0,
  doneTasks: 0,
  remainingTasks: 0,
  lateTasks: 0,
  blockedTasks: 0,
  validatedTasks: 0,
  validationRate: null,
  openIssues: 0,
  highIssues: 0,
  issueCount: 0,
  closeDuration: null,
  plannedDuration: 0,
};

export function buildFinancialClose(records: CloseRecord[]): CloseView {
  const periodIds = Array.from(new Set(records.map((record) => record.period))).sort();
  const asOf = periodIds.length > 0 ? periodIds[periodIds.length - 1] : null;

  const memoRows = records.filter((record) => record.kind === 'memo');
  const tasks = records
    .filter((record) => record.kind === 'task' && record.period === asOf)
    .sort((a, b) =>
      a.planned_start_day === b.planned_start_day
        ? a.planned_end_day - b.planned_end_day
        : a.planned_start_day - b.planned_start_day,
    );
  const issues = records
    .filter((record) => record.kind === 'issue')
    .sort((a, b) => (a.raised_date < b.raised_date ? 1 : -1));

  const isOpen = memoRows.some(
    (record) =>
      record.period === asOf && record.metric === 'open_period' && record.amount > 0,
  );

  // --- progress by area: every task counted once, at the state it is in.
  const areaKeys: string[] = [];
  for (const task of tasks) {
    if (!areaKeys.includes(task.area)) {
      areaKeys.push(task.area);
    }
  }
  const areas: AreaProgress[] = areaKeys
    .map((key) => {
      const inArea = tasks.filter((task) => task.area === key);
      const done = inArea.filter((task) => task.status === 'done').length;
      return {
        key,
        label: inArea[0].area_label,
        total: inArea.length,
        done,
        running: inArea.filter((task) => task.status === 'in_progress').length,
        blocked: inArea.filter((task) => task.status === 'blocked').length,
        notStarted: inArea.filter((task) => task.status === 'not_started').length,
        completion: inArea.length > 0 ? done / inArea.length : 0,
      };
    })
    .sort((a, b) => a.completion - b.completion || a.label.localeCompare(b.label));

  const statuses: StatusGroup[] = CLOSE_STATUSES.map((status) => {
    const count = tasks.filter((task) => task.status === status.key).length;
    return {
      key: status.key,
      label: status.label,
      count,
      share: tasks.length > 0 ? count / tasks.length : 0,
    };
  });

  const issueAreaKeys: string[] = [];
  for (const issue of issues) {
    if (!issueAreaKeys.includes(issue.area)) {
      issueAreaKeys.push(issue.area);
    }
  }
  const issueAreas: IssueGroup[] = issueAreaKeys
    .map((key) => {
      const inArea = issues.filter((issue) => issue.area === key);
      return {
        key,
        label: inArea[0].area_label,
        count: inArea.length,
        open: inArea.filter((issue) => !issue.is_resolved).length,
        high: inArea.filter((issue) => issue.severity === 'high').length,
      };
    })
    .sort((a, b) => b.count - a.count);

  const durations: CloseDurationPoint[] = periodIds.map((period) => {
    const metricOf = (metric: string) =>
      memoRows.find(
        (record) => record.period === period && record.metric === metric,
      )?.amount ?? 0;
    const actual = metricOf('close_duration_days');
    return {
      period,
      label: formatPeriodLabel(period),
      actual: actual > 0 ? actual : null,
      planned: metricOf('planned_duration_days'),
    };
  });

  const closed = durations.filter((point) => point.actual !== null);
  const done = tasks.filter((task) => task.status === 'done');
  const validated = tasks.filter((task) => task.is_validated).length;

  const kpis: CloseKpis =
    tasks.length === 0
      ? { ...EMPTY_KPIS, issueCount: issues.length }
      : {
          completion: done.length / tasks.length,
          taskCount: tasks.length,
          doneTasks: done.length,
          remainingTasks: tasks.length - done.length,
          lateTasks: tasks.filter((task) => task.is_late).length,
          blockedTasks: tasks.filter((task) => task.status === 'blocked').length,
          validatedTasks: validated,
          validationRate: done.length > 0 ? validated / done.length : null,
          openIssues: issues.filter((issue) => !issue.is_resolved).length,
          highIssues: issues.filter(
            (issue) => issue.severity === 'high' && !issue.is_resolved,
          ).length,
          issueCount: issues.length,
          closeDuration:
            closed.length > 0
              ? closed.reduce((sum, point) => sum + (point.actual ?? 0), 0) /
                closed.length
              : null,
          plannedDuration: durations[durations.length - 1]?.planned ?? 0,
        };

  // A running close has got as far as its last signed-off task; a month that
  // is already closed has no "now" left to draw.
  const progressDay =
    isOpen && done.length > 0
      ? Math.max(...done.map((task) => task.actual_end_day))
      : null;

  return {
    asOf,
    asOfLabel: asOf ? formatPeriodLabel(asOf) : '—',
    isOpen,
    progressDay,
    kpis,
    tasks,
    areas,
    statuses,
    issues,
    issueAreas,
    durations,
  };
}
