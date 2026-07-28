"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchColumnValues,
  isFilterActive,
  type ColumnFilters,
  type ColumnFilterState,
  type ColumnValue,
  type TweetSearchContext,
} from "@/lib/tweetSearch";

type Props = {
  column: string;
  label: string;
  /** True when this column's distinct values are worth listing as checkboxes. */
  faceted: boolean;
  state: ColumnFilterState;
  /** Every column's filters — the value list reflects the other columns. */
  filters: ColumnFilters;
  onChange: (next: ColumnFilterState) => void;
  /** Live graph search context; when null the values come from `localValues`. */
  search: TweetSearchContext | null;
  /** Distinct values derived from the loaded rows (static-export fallback). */
  localValues: ColumnValue[];
};

const EMPTY_LABEL = "(blank)";

export function ColumnFilter({
  column,
  label,
  faceted,
  state,
  filters,
  onChange,
  search,
  localValues,
}: Props) {
  const [open, setOpen] = useState(false);
  const [needle, setNeedle] = useState("");
  const [values, setValues] = useState<ColumnValue[]>([]);
  const [loading, setLoading] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [anchor, setAnchor] = useState({ top: 0, left: 0 });
  const rootRef = useRef<HTMLDivElement | null>(null);
  const btnRef = useRef<HTMLButtonElement | null>(null);

  const active = isFilterActive(state);

  // Close on outside click / Escape so the popover behaves like a menu.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // The table header is sticky inside a scrolling, clipping wrapper, so the
  // popover is fixed-positioned against the viewport and re-anchored whenever
  // anything scrolls or resizes (capture phase catches ancestor scrolls).
  useEffect(() => {
    if (!open) return;
    function place() {
      const rect = btnRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = 260;
      setAnchor({
        top: rect.bottom + 6,
        left: Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8)),
      });
    }
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  // Load the checkbox options: from the graph when a live context exists,
  // otherwise from the rows already loaded. Debounced on the search box.
  useEffect(() => {
    if (!open || !faceted) return;
    if (!search) {
      setValues(localValues);
      setTruncated(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      fetchColumnValues(search, column, needle, filters, controller.signal)
        .then((res) => {
          // null = no backend; fall back to the values in the loaded rows.
          setValues(res ? res.values : localValues);
          setTruncated(Boolean(res?.truncated));
        })
        .catch(() => {
          /* aborted by a newer keystroke */
        })
        .finally(() => setLoading(false));
    }, 200);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
    // `filters` is intentionally read fresh on each open/keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, faceted, search, column, needle, localValues]);

  // Without a backend the search box filters the local option list directly.
  const shown = useMemo(() => {
    if (search) return values;
    const q = needle.trim().toLowerCase();
    if (!q) return values;
    return values.filter((v) => v.value.toLowerCase().includes(q));
  }, [values, needle, search]);

  function toggle(value: string) {
    const next = state.values.includes(value)
      ? state.values.filter((v) => v !== value)
      : [...state.values, value];
    onChange({ ...state, values: next });
  }

  return (
    <div className="cf" ref={rootRef}>
      <button
        ref={btnRef}
        type="button"
        className={`cf-btn${active ? " is-active" : ""}`}
        aria-label={`Filter ${label}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span aria-hidden="true">▼</span>
      </button>
      {open ? (
        <div
          className="cf-pop"
          role="dialog"
          aria-label={`Filter ${label}`}
          style={{ top: anchor.top, left: anchor.left }}
        >
          <input
            className="cf-search"
            type="search"
            autoFocus
            placeholder={faceted ? `Search ${label}…` : `Contains…`}
            value={needle}
            onChange={(e) => setNeedle(e.target.value)}
          />
          {!faceted ? (
            <>
              <p className="cf-hint">
                {search
                  ? "Searches every tweet in the window, not just the loaded rows."
                  : "Filters the rows currently loaded."}
              </p>
              <div className="cf-actions">
                <button
                  type="button"
                  onClick={() => onChange({ ...state, contains: needle })}
                >
                  Apply
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setNeedle("");
                    onChange({ contains: "", values: [] });
                  }}
                >
                  Clear
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="cf-actions">
                <button
                  type="button"
                  onClick={() =>
                    onChange({ ...state, values: shown.map((v) => v.value) })
                  }
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={() => onChange({ contains: "", values: [] })}
                >
                  Clear
                </button>
              </div>
              <div className="cf-list">
                {loading ? (
                  <div className="cf-empty">Loading…</div>
                ) : !shown.length ? (
                  <div className="cf-empty">No values.</div>
                ) : (
                  shown.map((v) => (
                    <label className="cf-item" key={v.value || EMPTY_LABEL}>
                      <input
                        type="checkbox"
                        checked={state.values.includes(v.value)}
                        onChange={() => toggle(v.value)}
                      />
                      <span className="cf-item-label">
                        {v.value || EMPTY_LABEL}
                      </span>
                      <span className="cf-item-count">{v.count}</span>
                    </label>
                  ))
                )}
              </div>
              {truncated ? (
                <p className="cf-hint">
                  Showing the most frequent values — narrow with the search box.
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
