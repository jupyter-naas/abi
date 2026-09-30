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
  const res = await fetch(withAccessToken(`${BASE}/${path}`));
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

type Dashboards = Pick<Snapshots, "count" | "search">;

/**
 * What every page needs before it can paint: the filters and the timezone -
 * three small files. Nothing else is waited for; the graph totals and the
 * dashboards arrive on their own (`loadGraphTotals`, `loadDashboards`).
 */
export async function loadGlobals(): Promise<Snapshots> {
  const [scenarios, queries, timezone] = await Promise.all([
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
  ]);
  return {
    ...emptySnapshots(),
    updatedAt: scenarios.updated_at || queries.updated_at || null,
    scenarios: scenarios.scenarios || [],
    queries: queries.queries || [],
    timezones: timezone.timezones || [],
    defaultTimezone: timezone.default || "UTC",
  };
}

/**
 * How many posts the graph holds. Only a count line quotes it, so nothing
 * waits for it. Added after the rest: an older publish simply has no totals,
 * and the pages that quote them fall back to what they can count themselves.
 */
export async function loadGraphTotals(): Promise<GraphTotals | null> {
  const graph = await loadJson<Partial<GraphTotals>>("globals/graph.json").catch(
    () => null,
  );
  return graph
    ? {
        posts: graph.posts || 0,
        matched: graph.matched || 0,
        referenced: graph.referenced || 0,
      }
    : null;
}

/** The Count / Search Recent Tweets charts and tables - only those pages ask. */
export async function loadDashboards(): Promise<Dashboards> {
  const [cKpis, cBars, cLines, sKpis, sBars, sLines, sTables, sFacets] =
    await Promise.all([
      loadJson<{ kpis?: Snapshots["count"]["kpis"] }>(
        "count_recent_tweets/kpis.json",
      ),
      loadJson<{ barcharts?: Snapshots["count"]["barcharts"] }>(
        "count_recent_tweets/barcharts.json",
      ),
      loadJson<{ linecharts?: Snapshots["count"]["linecharts"] }>(
        "count_recent_tweets/linecharts.json",
      ),
      loadJson<{ kpis?: Snapshots["search"]["kpis"] }>(
        "search_recents_tweets/kpis.json",
      ),
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
    ]);
  return {
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
