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
  /** Rendered instead of ``value`` when set (dates and other non-numerics). */
  text?: string;
  prev_value?: number | null;
  delta?: number | null;
  hint?: string;
  unit?: string;
  cap?: number;
  /**
   * Split of an ingestion KPI whose ``value`` is the total of both. ``matched``
   * are the posts that answered the search query; ``referenced`` are the reply
   * parents, quoted tweets and retweeted originals returned only as context.
   */
  matched?: number;
  referenced?: number;
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
  label?: string;
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

/** One row of the Search page tweet table. */
export type TweetRow = {
  created_at: string;
  text: string;
  url: string;
  username: string;
  location: string;
  verified_type: string;
  /** Space-separated media URLs; only the Users page's post table fills this. */
  media_url?: string;
};

export type TableEntry = {
  id: string;
  query_slug: string;
  scenario_id: string;
  columns: TableColumn[];
  rows: Record<string, unknown>[];
};

/** Public metrics of an X account (all optional — stubs carry none). */
export type UserMetrics = {
  followers_count: number | null;
  following_count: number | null;
  tweet_count: number | null;
  listed_count: number | null;
  like_count: number | null;
  media_count: number | null;
};

/** The XUser individual behind an author, as stored in the graph. */
export type UserAccount = {
  author_id?: string;
  display_name?: string;
  description?: string;
  user_url?: string;
  user_created_at?: string;
  profile_image_url?: string;
  profile_banner_url?: string;
  verified?: boolean | null;
  is_identity_verified?: boolean | null;
  protected?: boolean | null;
  pinned_tweet_id?: string;
  most_recent_tweet_id?: string;
  metrics?: UserMetrics;
};

/** One author in the search index, aggregated over the whole tweet graph. */
export type UserRow = {
  username: string;
  posts: number;
  last_post_at: string;
  location: string;
  verified_type: string;
  /** Account bio, truncated by the publisher. Empty for the many stubs. */
  description?: string;
};

/**
 * An author's published record: totals + account fields + every post.
 *
 * Everything but the username is optional — the publisher drops empty fields
 * rather than writing placeholders, since most authors are ingested as
 * tweet-author stubs and at ~60k of them the placeholders dominate the file.
 */
export type UserProfile = Partial<UserRow> &
  UserAccount & {
    username: string;
    first_post_at?: string;
  };

export type UserBundle = {
  profile: UserProfile;
  posts: TweetRow[];
};

/** Distinct values of one faceted column, published per query + scenario. */
export type FacetValue = {
  value: string;
  count: number;
};

export type FacetEntry = {
  query_slug: string;
  scenario_id: string;
  column: string;
  values: FacetValue[];
  truncated?: boolean;
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
    /** Column-filter value lists, aggregated over the whole window. */
    facets: FacetEntry[];
  };
};

export type PageKey = "count" | "search" | "users" | "parameters";
