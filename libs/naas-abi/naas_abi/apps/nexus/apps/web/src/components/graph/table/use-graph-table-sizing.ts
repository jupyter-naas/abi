'use client';

import { useEffect, useLayoutEffect, useRef, useState, type MutableRefObject, type PointerEvent as ReactPointerEvent } from 'react';

export type GraphTableWidths = Record<string, number>;
interface SizingColumn {
  id: string;
  width?: number;
  minWidth?: number;
}

/** Shared with Composer: freeze initial widths, then resize only the chosen column. */
export function useGraphTableSizing(
  columns: SizingColumn[],
  retainedWidths?: MutableRefObject<GraphTableWidths>,
) {
  const tableRef = useRef<HTMLTableElement>(null);
  const thRefs = useRef<Record<string, HTMLTableCellElement | null>>({});
  const resizingRef = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);
  const [colWidths, setColWidths] = useState<GraphTableWidths>(() => ({ ...retainedWidths?.current }));
  const [activeResizeCol, setActiveResizeCol] = useState<string | null>(null);
  const measured = columns.every((col) => colWidths[col.id] !== undefined);
  const totalWidth = columns.reduce((sum, col) => sum + (colWidths[col.id] ?? col.width ?? 160), 0);
  const columnSet = JSON.stringify(columns.map((col) => col.id).sort());

  const minWidth = (id: string) => columns.find((col) => col.id === id)?.minWidth ?? 64;
  const setWidth = (id: string, width: number) => {
    const next = Math.max(minWidth(id), Math.round(width));
    if (retainedWidths) retainedWidths.current[id] = next;
    setColWidths((prev) => ({ ...prev, [id]: next }));
  };

  useLayoutEffect(() => {
    if (measured) return;
    const next = { ...colWidths };
    for (const col of columns) {
      next[col.id] ??= Math.max(
        col.minWidth ?? 64,
        col.width ?? Math.round(thRefs.current[col.id]?.getBoundingClientRect().width || 160),
      );
    }
    if (retainedWidths) retainedWidths.current = { ...next };
    setColWidths(next);
  }, [columns, colWidths, measured, retainedWidths]);

  // A query change, cancelled gesture, or unmount must not leave the body in resize mode.
  useEffect(() => () => cleanupRef.current?.(), [columnSet]);

  const startResize = (event: ReactPointerEvent, id: string) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    cleanupRef.current?.();
    resizingRef.current = true;
    setActiveResizeCol(id);
    const startX = event.clientX;
    const startWidth = colWidths[id] ?? thRefs.current[id]?.getBoundingClientRect().width ?? 160;
    const pointerId = event.pointerId;
    const previousCursor = document.body.style.cursor;
    const previousSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (e: PointerEvent) => {
      if (e.pointerId === pointerId) setWidth(id, startWidth + e.clientX - startX);
    };
    const stop = () => {
      resizingRef.current = false;
      setActiveResizeCol(null);
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousSelect;
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onEnd);
      window.removeEventListener('pointercancel', onEnd);
      window.removeEventListener('blur', stop);
      cleanupRef.current = null;
    };
    const onEnd = (e: PointerEvent) => {
      if (e.pointerId === pointerId) stop();
    };
    cleanupRef.current = stop;
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
    window.addEventListener('blur', stop);
  };

  const autoFit = (id: string) => {
    const table = tableRef.current;
    const index = columns.findIndex((col) => col.id === id);
    if (!table || index < 0) return;
    // Measure real cell typography in the same theme, without truncation or resize controls.
    const probe = table.cloneNode(false) as HTMLTableElement;
    probe.removeAttribute('id');
    probe.removeAttribute('style');
    probe.classList.add('graph-table-measure');
    probe.setAttribute('aria-hidden', 'true');
    probe.inert = true;
    for (const row of Array.from(table.rows)) {
      const cell = row.cells[index];
      if (!cell || cell.colSpan !== 1) continue;
      const clone = cell.cloneNode(true) as HTMLTableCellElement;
      clone.querySelectorAll('[data-column-resize]').forEach((handle) => handle.remove());
      clone.removeAttribute('id');
      clone.querySelectorAll('[id]').forEach((node) => node.removeAttribute('id'));
      const section = probe.querySelector(row.parentElement!.tagName) ??
        probe.appendChild(document.createElement(row.parentElement!.tagName));
      section.appendChild(document.createElement('tr')).appendChild(clone);
    }
    table.parentElement!.appendChild(probe);
    try {
      // Bound automatic expansion for exceptionally long values; manual resizing is unrestricted.
      setWidth(id, Math.min(800, Math.ceil(probe.getBoundingClientRect().width) + 8));
    } finally {
      probe.remove();
    }
  };

  return { tableRef, thRefs, resizingRef, colWidths, measured, totalWidth, activeResizeCol, startResize, setWidth, autoFit, minWidth };
}

export type GraphTableSizing = ReturnType<typeof useGraphTableSizing>;
