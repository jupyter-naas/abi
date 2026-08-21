"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  isFilterActive,
  type ColumnFilterState,
  type ColumnValue,
} from "@/lib/tweetSearch";

type Props = {
  label: string;
  /** True when this column's distinct values are worth listing as checkboxes. */
  faceted: boolean;
  state: ColumnFilterState;
  onChange: (next: ColumnFilterState) => void;
  /**
   * The checkbox options: the published facet list for this column when there
   * is one, otherwise the distinct values of the rows currently loaded.
   */
  values: ColumnValue[];
  /** True when the published list was capped at the publisher's limit. */
  truncated?: boolean;
};

const EMPTY_LABEL = "(blank)";

export function ColumnFilter({
  label,
  faceted,
  state,
  onChange,
  values,
  truncated = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [needle, setNeedle] = useState("");
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

  // The options are already in memory, so the search box narrows them directly.
  const shown = useMemo(() => {
    const q = needle.trim().toLowerCase();
    if (!q) return values;
    return values.filter((v) => v.value.toLowerCase().includes(q));
  }, [values, needle]);

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
              <p className="cf-hint">Filters the rows currently loaded.</p>
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
                {!shown.length ? (
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
