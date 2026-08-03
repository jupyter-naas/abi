export type Scenario = {
  id: string;
  label: string;
  start_time: string;
  end_time: string;
};

export type QueryEntry = {
  slug: string;
  query: string;
  label?: string;
};

export type TimezoneEntry = {
  id: string;
  label: string;
};

export type KpiItem = {
  id: string;
  label: string;
  value: number | null;
  prev_value?: number | null;
  delta?: number | null;
  hint?: string;
  unit?: string;
  cap?: number;
};

export type KpiEntry = {
  query_slug: string;
  scenario_id: string;
  items: KpiItem[];
};

export type Bar = {
  label: string;
  value: number;
  delta?: number | null;
  href?: string;
};

export type BarchartItem = {
  id: string;
  bars: Bar[];
};

export type BarchartEntry = {
  query_slug: string;
  scenario_id: string;
  items: BarchartItem[];
};

export type ChartPoint = {
  t: string;
  value: number;
  label: string;
  range_label?: string;
};

export type ChartSeries = {
  id: "current" | "previous" | string;
  points: ChartPoint[];
};

export type LinechartEntry = {
  query_slug: string;
  scenario_id: string;
  granularity?: string;
  series: ChartSeries[];
};

export type TableColumn = {
  key: string;
  label: string;
};

export type TableEntry = {
  id: string;
  query_slug: string;
  scenario_id: string;
  columns: TableColumn[];
  rows: Record<string, unknown>[];
};

export type Snapshots = {
  updatedAt: string | null;
  scenarios: Scenario[];
  queries: QueryEntry[];
  timezones: TimezoneEntry[];
  defaultTimezone: string;
  count: {
    kpis: KpiEntry[];
    barcharts: BarchartEntry[];
    linecharts: LinechartEntry[];
  };
  search: {
    kpis: KpiEntry[];
    barcharts: BarchartEntry[];
    linecharts: LinechartEntry[];
    tables: TableEntry[];
  };
};

export type PageKey = "count" | "search" | "parameters";
