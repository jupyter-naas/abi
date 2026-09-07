import type { GraphTotals, Snapshots } from "@/lib/types";
import { withAccessToken } from "@/lib/routes";

/** Minimal snapshot shape so the shell renders when JSON is missing or fetch fails. */
export function emptySnapshots(): Snapshots {
  return {
    updatedAt: null,
    graph: null,
    scenarios: [],
    queries: [],
    timezones: [{ id: "UTC", label: "UTC" }],
    defaultTimezone: "UTC",
    count: { kpis: [], barcharts: [], linecharts: [] },
    search: { kpis: [], barcharts: [], linecharts: [], tables: [], facets: [] },
  };
}

/** Snapshot JSON lives next to the exported index under /app-html/x/apps/x_proxy/. */
const BASE = "/app-html/x/apps/x_proxy";

async function loadJson<T>(path: string): Promise<T> {
  const res = await fetch(withAccessToken(`${BASE}/${path}`), { cache: "no-store" });
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
    sFacets,
    graph,
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
    // Added after the other search-page files - an older publish simply has no
    // facets, and the column filters then fall back to the loaded rows.
    loadJson<{ facets?: Snapshots["search"]["facets"] }>(
      "search_recents_tweets/facets.json",
    ).catch(() => ({ facets: [] })),
    // Added after the rest: an older publish simply has no totals, and the
    // pages that quote them fall back to what they can count themselves.
    loadJson<Partial<GraphTotals>>("globals/graph.json").catch(() => null),
  ]);

  return {
    updatedAt: scenarios.updated_at || queries.updated_at || null,
    graph: graph
      ? {
          posts: graph.posts || 0,
          matched: graph.matched || 0,
          referenced: graph.referenced || 0,
        }
      : null,
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
      facets: sFacets.facets || [],
    },
  };
}
