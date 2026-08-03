import type { Snapshots } from "@/lib/types";

/** Snapshot JSON lives next to the exported index under /app-html/x/apps/x/. */
const BASE = "/app-html/x/apps/x";

async function loadJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export async function loadSnapshots(): Promise<Snapshots> {
  const [
    scenarios,
    queries,
    timezone,
    cKpis,
    cBars,
    cLines,
    sKpis,
    sBars,
    sLines,
    sTables,
  ] = await Promise.all([
    loadJson<{ updated_at?: string; scenarios?: Snapshots["scenarios"] }>(
      "globals/scenarios.json",
    ),
    loadJson<{ updated_at?: string; queries?: Snapshots["queries"] }>(
      "globals/queries.json",
    ),
    loadJson<{
      updated_at?: string;
      default?: string;
      timezones?: Snapshots["timezones"];
    }>("globals/timezone.json"),
    loadJson<{ kpis?: Snapshots["count"]["kpis"] }>("count_recent_tweets/kpis.json"),
    loadJson<{ barcharts?: Snapshots["count"]["barcharts"] }>(
      "count_recent_tweets/barcharts.json",
    ),
    loadJson<{ linecharts?: Snapshots["count"]["linecharts"] }>(
      "count_recent_tweets/linecharts.json",
    ),
    loadJson<{ kpis?: Snapshots["search"]["kpis"] }>("search_recents_tweets/kpis.json"),
    loadJson<{ barcharts?: Snapshots["search"]["barcharts"] }>(
      "search_recents_tweets/barcharts.json",
    ),
    loadJson<{ linecharts?: Snapshots["search"]["linecharts"] }>(
      "search_recents_tweets/linecharts.json",
    ),
    loadJson<{ tables?: Snapshots["search"]["tables"] }>(
      "search_recents_tweets/tables.json",
    ),
  ]);

  return {
    updatedAt: scenarios.updated_at || queries.updated_at || null,
    scenarios: scenarios.scenarios || [],
    queries: queries.queries || [],
    timezones: timezone.timezones || [],
    defaultTimezone: timezone.default || "UTC",
    count: {
      kpis: cKpis.kpis || [],
      barcharts: cBars.barcharts || [],
      linecharts: cLines.linecharts || [],
    },
    search: {
      kpis: sKpis.kpis || [],
      barcharts: sBars.barcharts || [],
      linecharts: sLines.linecharts || [],
      tables: sTables.tables || [],
    },
  };
}
