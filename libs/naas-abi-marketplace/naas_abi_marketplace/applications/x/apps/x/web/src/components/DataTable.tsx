"use client";

import { useMemo, useState } from "react";
import type { TableEntry } from "@/lib/types";

type Props = {
  table: TableEntry | null;
  timezone: string;
  /** When true, nest ``url`` under the Text cell and hide the URL column. */
  nestUrlUnderText?: boolean;
};

export function DataTable({
  table,
  timezone,
  nestUrlUnderText = false,
}: Props) {
  const [q, setQ] = useState("");
  const allColumns = table?.columns || [];
  const columns = useMemo(() => {
    if (!nestUrlUnderText) return allColumns;
    return allColumns.filter((c) => c.key !== "url");
  }, [allColumns, nestUrlUnderText]);
  const rows = table?.rows || [];

  const view = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((r) =>
      allColumns.some((c) =>
        String(r[c.key] ?? "")
          .toLowerCase()
          .includes(needle),
      ),
    );
  }, [q, rows, allColumns]);

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
      </div>
      <div className="dt-wrap">
        <table className="dt">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key}>{c.label}</th>
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
              view.slice(0, 200).map((r, i) => (
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
