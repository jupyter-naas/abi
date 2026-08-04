"use client";

import { useEffect, useMemo, useState } from "react";
import { ColumnFilter } from "@/components/ColumnFilter";
import {
  activeFilterCount,
  FACET_COLUMNS,
  fetchTweets,
  isFilterActive,
  type ColumnFilters,
  type ColumnFilterState,
  type ColumnValue,
  type TweetSearchContext,
} from "@/lib/tweetSearch";
import type { TableEntry } from "@/lib/types";

type Props = {
  table: TableEntry | null;
  timezone: string;
  /** When true, nest ``url`` under the Text cell and hide the URL column. */
  nestUrlUnderText?: boolean;
  /**
   * Live graph-search context. When set, column filters are pushed into SPARQL
   * so they return the newest matching tweets across the whole window instead
   * of narrowing the snapshot page. Omit for snapshot-only tables.
   */
  search?: TweetSearchContext | null;
};

/** Rows rendered at once — the DOM cost is what's capped here, not the query. */
const MAX_RENDERED_ROWS = 1000;

const EMPTY_FILTER: ColumnFilterState = { contains: "", values: [] };

/** Thumbnails rendered per cell before collapsing the rest into a "+N". */
const MAX_MEDIA_THUMBS = 4;

export function DataTable({
  table,
  timezone,
  nestUrlUnderText = false,
  search = null,
}: Props) {
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState<ColumnFilters>({});
  const [liveRows, setLiveRows] = useState<Record<string, unknown>[] | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [offline, setOffline] = useState(false);

  const allColumns = table?.columns || [];
  const columns = useMemo(() => {
    if (!nestUrlUnderText) return allColumns;
    return allColumns.filter((c) => c.key !== "url");
  }, [allColumns, nestUrlUnderText]);

  const snapshotRows = useMemo(() => table?.rows || [], [table]);
  const activeCount = activeFilterCount(filters);

  // Reset when the table identity changes (query / scenario switch) so filters
  // from the previous selection never leak into the new one.
  const tableKey = `${table?.id}:${table?.query_slug}:${table?.scenario_id}`;
  useEffect(() => {
    setFilters({});
    setLiveRows(null);
    setTruncated(false);
    setQ("");
  }, [tableKey]);

  // Push the active filters into the graph. Debounced so typing in a column
  // search box doesn't fire a SPARQL query per keystroke.
  useEffect(() => {
    if (!search) return;
    if (!activeCount) {
      // No filters — the snapshot already holds the newest page.
      setLiveRows(null);
      setTruncated(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      fetchTweets(search, filters, controller.signal)
        .then((res) => {
          if (!res) {
            // No backend: fall back to narrowing the snapshot rows.
            setOffline(true);
            setLiveRows(null);
            return;
          }
          setOffline(false);
          setLiveRows(res.rows as Record<string, unknown>[]);
          setTruncated(res.truncated);
        })
        .catch(() => {
          /* superseded by a newer request */
        })
        .finally(() => setLoading(false));
    }, 250);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [search, filters, activeCount]);

  const liveMode = Boolean(search) && !offline;

  // In live mode the server already applied the column filters; otherwise
  // apply them here against whichever rows we have.
  const filtered = useMemo(() => {
    const base = liveRows ?? snapshotRows;
    if (liveMode && liveRows) return base;
    if (!activeCount) return base;
    return base.filter((row) =>
      Object.entries(filters).every(([column, state]) => {
        if (!isFilterActive(state)) return true;
        const cell = String(row[column] ?? "");
        if (
          state.contains.trim() &&
          !cell.toLowerCase().includes(state.contains.trim().toLowerCase())
        ) {
          return false;
        }
        if (state.values.length && !state.values.includes(cell)) return false;
        return true;
      }),
    );
  }, [liveRows, snapshotRows, liveMode, filters, activeCount]);

  // The toolbar box always narrows what is on screen, across every column.
  const view = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return filtered;
    return filtered.filter((r) =>
      allColumns.some((c) =>
        String(r[c.key] ?? "")
          .toLowerCase()
          .includes(needle),
      ),
    );
  }, [q, filtered, allColumns]);

  // Distinct values from the loaded rows — the option list when there is no
  // backend to enumerate the graph.
  const localValues = useMemo(() => {
    const out: Record<string, ColumnValue[]> = {};
    for (const column of FACET_COLUMNS) {
      const counts = new Map<string, number>();
      for (const row of snapshotRows) {
        const value = String(row[column] ?? "");
        counts.set(value, (counts.get(value) || 0) + 1);
      }
      out[column] = [...counts.entries()]
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => b.count - a.count);
    }
    return out;
  }, [snapshotRows]);

  const filterable = Boolean(search) || activeCount > 0;

  return (
    <div>
      <div className="dt-toolbar">
        <input
          className="dt-search"
          type="search"
          placeholder="Search…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="dt-status">
          {loading ? <span className="dt-loading">Searching…</span> : null}
          {activeCount ? (
            <>
              <span>
                {view.length.toLocaleString()} row(s) · {activeCount} filter(s)
                {truncated ? " · capped" : ""}
              </span>
              <button
                type="button"
                className="dt-clear"
                onClick={() => setFilters({})}
              >
                Clear filters
              </button>
            </>
          ) : null}
        </div>
      </div>
      <div className="dt-wrap">
        <table className="dt">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>
                  <span className="dt-th">
                    <span className="dt-th-label">{c.label}</span>
                    {filterable ? (
                      <ColumnFilter
                        column={c.key}
                        label={c.label}
                        faceted={FACET_COLUMNS.includes(c.key)}
                        state={filters[c.key] || EMPTY_FILTER}
                        filters={filters}
                        onChange={(next) =>
                          setFilters((prev) => ({ ...prev, [c.key]: next }))
                        }
                        search={search}
                        localValues={localValues[c.key] || []}
                      />
                    ) : null}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!view.length ? (
              <tr>
                <td className="empty" colSpan={Math.max(1, columns.length)}>
                  No rows.
                </td>
              </tr>
            ) : (
              view.slice(0, MAX_RENDERED_ROWS).map((r, i) => (
                <tr key={i}>
                  {columns.map((c) => (
                    <td key={c.key}>
                      {renderCell(c.key, r, timezone, nestUrlUnderText)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {view.length > MAX_RENDERED_ROWS ? (
        <p className="dt-note">
          Showing the first {MAX_RENDERED_ROWS.toLocaleString()} of{" "}
          {view.length.toLocaleString()} rows.
        </p>
      ) : null}
    </div>
  );
}

/** Thumbnails for a tweet's attached media, linking to the full asset. */
function MediaCell({ value }: { value: string }) {
  const [broken, setBroken] = useState<Record<string, boolean>>({});
  const urls = value.split(/\s+/).filter(Boolean);
  if (!urls.length) return <>—</>;
  const shown = urls.slice(0, MAX_MEDIA_THUMBS);
  return (
    <div className="dt-media-cell">
      {shown.map((href) => (
        <a
          key={href}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          title="Open media"
        >
          {broken[href] ? (
            // The asset is gone (or blocked) — keep the link reachable.
            <span className="dt-media-fallback">media</span>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              className="dt-media-thumb"
              src={href}
              alt=""
              loading="lazy"
              onError={() => setBroken((prev) => ({ ...prev, [href]: true }))}
            />
          )}
        </a>
      ))}
      {urls.length > shown.length ? (
        <span className="dt-media-more">+{urls.length - shown.length}</span>
      ) : null}
    </div>
  );
}

function renderCell(
  key: string,
  row: Record<string, unknown>,
  timezone: string,
  nestUrlUnderText: boolean,
): React.ReactNode {
  const v = row[key];

  if (key === "text" && nestUrlUnderText) {
    const text =
      v == null || v === "" ? "—" : String(v);
    const url = typeof row.url === "string" ? row.url : "";
    return (
      <div className="dt-text-cell">
        <div className="dt-text-body">{text}</div>
        {url ? (
          <a
            className="dt-text-url"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {url}
          </a>
        ) : null}
      </div>
    );
  }

  if (key === "media_url") {
    return <MediaCell value={String(v ?? "")} />;
  }

  if (key === "url" && typeof v === "string" && v) {
    return (
      <a href={v} target="_blank" rel="noopener noreferrer">
        {v}
      </a>
    );
  }
  if (key === "username" && typeof v === "string" && v && v !== "—") {
    return (
      <a
        href={`https://x.com/${v}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        @{v}
      </a>
    );
  }
  if (key === "created_at" && typeof v === "string" && v) {
    try {
      return new Date(v).toLocaleString(undefined, { timeZone: timezone });
    } catch {
      return v;
    }
  }
  if (v == null || v === "") return "—";
  return String(v);
}
