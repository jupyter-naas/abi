'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Undo2, Redo2, Copy, Trash2 } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { address, cellInput, columnLabel, copyRange, parseAddress, parseClipboard, patchCells, readWorkbook, renameSheet, uniqueSheetName, writeWorkbook, type Cell, type Position, type Workbook } from './workbook-model';
import { sheetAxis } from './workbook-layout';
import './workbook-grid.css';

export function WorkbookGrid({ html, workspaceId, selectedIndex, onSelect, onChange, disabled = false }: {
  html: string; workspaceId: string; selectedIndex: number; onSelect: (index: number) => void;
  onChange: (html: string) => void; disabled?: boolean;
}) {
  const model = useMemo(() => readWorkbook(html), [html]);
  const index = Math.min(selectedIndex, (model?.sheets.length ?? 1) - 1);
  const [active, setActive] = useState<Position>({ row: 0, col: 0 });
  const [end, setEnd] = useState<Position>({ row: 0, col: 0 });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [editSource, setEditSource] = useState<'cell' | 'bar'>('cell');
  const formulaBar = useRef<HTMLInputElement>(null);
  const pointRef = useRef<{ start: number; end: number; cell: Position } | null>(null);
  const [pointed, setPointed] = useState<Position | null>(null);
  const [resize, setResize] = useState<{ axis: 'column_widths' | 'row_heights'; index: number; start: number; original: number; value: number } | null>(null);
  const resizeRef = useRef(resize);
  const clearPoint = () => { pointRef.current = null; setPointed(null); };
  const updateDraft = (value: string) => { setDraft(value); clearPoint(); };
  const beginEdit = (value: string) => { cancelBlur.current = false; clearPoint(); setEditSource('cell'); setDraft(value); setEditing(true); };
  const [nameBox, setNameBox] = useState('A1');
  const [showFormulas, setShowFormulas] = useState(false);
  const [message, setMessage] = useState('');
  const [computed, setComputed] = useState<{ html: string; model: Workbook } | null>(null);
  const [history, setHistory] = useState<{ past: string[]; future: string[] }>({ past: [], future: [] });
  const ownHtml = useRef(html);
  const [scroll, setScroll] = useState({ top: 0, left: 0 });
  const viewport = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 1000, height: 600 });
  const editor = useRef<HTMLInputElement>(null);
  const dragging = useRef(false);
  const cancelBlur = useRef(false);
  const raw = model?.sheets[index]?.rows[active.row]?.[active.col] ?? '';
  const rowHeight = 28; const colWidth = 120; const gutter = 48;
  const rows = Math.max(100, (model?.sheets[index]?.rows.length ?? 0) + 30, active.row + 30);
  const cols = Math.max(26, ...(model?.sheets[index]?.rows.map(r => r.length) ?? [0]), active.col + 5);
  const sheet = model?.sheets[index];
  const horizontal = sheetAxis(cols, colWidth, { ...sheet?.column_widths, ...(resize?.axis === 'column_widths' ? { [resize.index]: resize.value } : {}) });
  const vertical = sheetAxis(rows, rowHeight, { ...sheet?.row_heights, ...(resize?.axis === 'row_heights' ? { [resize.index]: resize.value } : {}) });
  const firstRow = Math.max(0, vertical.at(scroll.top) - 3);
  const lastRow = Math.min(rows, vertical.at(scroll.top + size.height) + 5);
  const firstCol = Math.max(0, horizontal.at(scroll.left) - 2);
  const lastCol = Math.min(cols, horizontal.at(scroll.left + size.width) + 4);
  const visibleRows = Array.from({ length: Math.max(0, lastRow - firstRow) }, (_, r) => r + firstRow);
  const visibleCols = Array.from({ length: Math.max(0, lastCol - firstCol) }, (_, c) => c + firstCol);
  if (editing && !visibleRows.includes(active.row)) visibleRows.push(active.row);
  if (editing && !visibleCols.includes(active.col)) visibleCols.push(active.col);

  useEffect(() => {
    const host = viewport.current;
    if (!host || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => setSize({ width: host.clientWidth, height: host.clientHeight }));
    observer.observe(host); return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (ownHtml.current !== html) { setHistory({ past: [], future: [] }); ownHtml.current = html; }
  }, [html]);
  useEffect(() => { setDraft(String(raw)); }, [raw, active.row, active.col, index]);
  useEffect(() => { setNameBox(address(active)); }, [active]);
  useEffect(() => {
    setActive({ row: 0, col: 0 }); setEnd({ row: 0, col: 0 }); setEditing(false);
    viewport.current?.scrollTo?.({ top: 0, left: 0 });
  }, [index]);
  useEffect(() => {
    const release = () => { dragging.current = false; };
    window.addEventListener('pointerup', release); return () => window.removeEventListener('pointerup', release);
  }, []);
  useEffect(() => {
    if (editing && editSource === 'cell') { editor.current?.focus(); editor.current?.setSelectionRange(editor.current.value.length, editor.current.value.length); }
  }, [editing, editSource]);
  useEffect(() => {
    if (!model || !workspaceId) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch('/api/sheets/evaluate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
          body: JSON.stringify({ workspace_id: workspaceId, html }),
        });
        if (!res.ok) throw new Error('Calculation unavailable; formulas are preserved.');
        const data = await res.json();
        if (!controller.signal.aborted) {
          setComputed({ html, model: data.workbook });
          setMessage(data.errors.length ? `${data.errors.length} formula error(s). Select a formula to inspect it.` : '');
        }
      } catch (error) { if (!controller.signal.aborted) setMessage((error as Error).message); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [html, workspaceId, model]);

  if (!model) return <div className="sheets-grid-empty" role="alert">This workbook has no valid spreadsheet data. Open Code to inspect it or ask SheetsAgent to repair it.</div>;
  const publish = (next: Workbook) => {
    if (disabled) return;
    const nextHtml = writeWorkbook(html, next);
    if (nextHtml === html) return;
    setHistory(h => ({ past: [...h.past.slice(-49), html], future: [] }));
    ownHtml.current = nextHtml; onChange(nextHtml);
  };
  const commit = () => {
    if (cancelBlur.current) { cancelBlur.current = false; return; }
    if (draft !== String(raw)) publish(patchCells(model, index, active, [[cellInput(draft)]]));
    setEditing(false); clearPoint();
  };
  const select = (p: Position, extend = false) => {
    if (editing) commit();
    if (!extend) setActive(p);
    setEnd(p); setEditing(false);
  };
  const navigate = (r: number, c: number, extend = false) => {
    const p = { row: Math.max(0, Math.min(1048575, r)), col: Math.max(0, Math.min(16383, c)) };
    select(p, extend);
    const host = viewport.current;
    if (!host) return;
    const top = vertical.offset(p.row); const left = horizontal.offset(p.col);
    if (top < host.scrollTop) host.scrollTop = top;
    else if (top + vertical.size(p.row) + rowHeight > host.scrollTop + host.clientHeight) host.scrollTop = top + vertical.size(p.row) + rowHeight - host.clientHeight;
    if (left < host.scrollLeft) host.scrollLeft = left;
    else if (left + horizontal.size(p.col) + gutter > host.scrollLeft + host.clientWidth) host.scrollLeft = left + horizontal.size(p.col) + gutter - host.clientWidth;
  };
  const pickCell = (cell: Position) => {
    const input = editSource === 'bar' ? formulaBar.current : editor.current;
    if (!input || !draft.startsWith('=')) return;
    const start = pointRef.current?.start ?? input.selectionStart ?? draft.length;
    const finish = pointRef.current?.end ?? input.selectionEnd ?? start;
    const reference = address(cell);
    setDraft(draft.slice(0, start) + reference + draft.slice(finish));
    pointRef.current = { start, end: start + reference.length, cell };
    setPointed(cell);
    requestAnimationFrame(() => { input.focus(); input.setSelectionRange(start + reference.length, start + reference.length); });
    const host = viewport.current;
    if (host) {
      const top = vertical.offset(cell.row); const left = horizontal.offset(cell.col);
      if (top < host.scrollTop) host.scrollTop = top;
      else if (top + vertical.size(cell.row) + rowHeight > host.scrollTop + host.clientHeight) host.scrollTop = top + vertical.size(cell.row) + rowHeight - host.clientHeight;
      if (left < host.scrollLeft) host.scrollLeft = left;
      else if (left + horizontal.size(cell.col) + gutter > host.scrollLeft + host.clientWidth) host.scrollLeft = left + horizontal.size(cell.col) + gutter - host.clientWidth;
    }
  };
  const editKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const moves: Record<string, [number, number]> = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
    const caret = e.currentTarget.selectionStart ?? draft.length;
    if (draft.startsWith('=') && moves[e.key] && !e.altKey && !e.ctrlKey && !e.metaKey && (pointRef.current || /[=+*/^(,;:<>&-]\s*$/.test(draft.slice(0, caret)))) {
      e.preventDefault(); e.stopPropagation();
      const from = pointRef.current?.cell ?? active; const [r, c] = moves[e.key];
      pickCell({ row: Math.max(0, Math.min(rows - 1, from.row + r)), col: Math.max(0, Math.min(cols - 1, from.col + c)) });
    } else if (e.key === 'Escape') {
      e.preventDefault(); cancelBlur.current = true; setDraft(String(raw)); clearPoint(); setEditing(false); viewport.current?.focus();
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault(); commit(); cancelBlur.current = true;
      const p = { row: Math.max(0, active.row + (e.key === 'Enter' ? (e.shiftKey ? -1 : 1) : 0)), col: Math.max(0, active.col + (e.key === 'Tab' ? (e.shiftKey ? -1 : 1) : 0)) };
      setActive(p); setEnd(p); viewport.current?.focus();
    } else if (moves[e.key] || e.key === 'Home' || e.key === 'End') clearPoint();
  };
  const saveDimension = (axis: 'column_widths' | 'row_heights', i: number, value: number) => {
    const next = structuredClone(model);
    next.sheets[index][axis] = { ...next.sheets[index][axis], [i]: value };
    publish(next);
  };
  const resizeHandle = (axis: 'column_widths' | 'row_heights', i: number) => {
    const column = axis === 'column_widths';
    const current = column ? horizontal.size(i) : vertical.size(i);
    const clamp = (value: number) => Math.round(Math.max(column ? 40 : 20, Math.min(column ? 1000 : 400, value)));
    return <span role="separator" aria-label={`Resize ${column ? `column ${columnLabel(i)}` : `row ${i + 1}`}`} aria-orientation={column ? 'vertical' : 'horizontal'} aria-valuenow={current} aria-valuemin={column ? 40 : 20} aria-valuemax={column ? 1000 : 400} tabIndex={disabled ? -1 : 0}
      className={column ? 'sheets-column-resize' : 'sheets-row-resize'}
      onPointerDown={e => { if (disabled) return; e.preventDefault(); e.stopPropagation(); e.currentTarget.setPointerCapture?.(e.pointerId); const next = { axis, index: i, start: column ? e.clientX : e.clientY, original: current, value: current }; resizeRef.current = next; setResize(next); }}
      onPointerMove={e => { const start = resizeRef.current; if (!start) return; const next = { ...start, value: clamp(start.original + (column ? e.clientX : e.clientY) - start.start) }; resizeRef.current = next; setResize(next); }}
      onPointerUp={e => { const next = resizeRef.current; if (!next) return; e.currentTarget.releasePointerCapture?.(e.pointerId); resizeRef.current = null; setResize(null); saveDimension(next.axis, next.index, next.value); }}
      onPointerCancel={() => { resizeRef.current = null; setResize(null); }}
      onKeyDown={e => { if (disabled) return; const delta = e.key === (column ? 'ArrowRight' : 'ArrowDown') ? 10 : e.key === (column ? 'ArrowLeft' : 'ArrowUp') ? -10 : 0; if (delta) { e.preventDefault(); e.stopPropagation(); saveDimension(axis, i, clamp(current + delta)); } }} />;
  };
  const undo = (redo = false) => {
    const stack = redo ? history.future : history.past;
    const next = stack.at(-1); if (!next || disabled) return;
    setEditing(false);
    setHistory(redo ? { past: [...history.past, html], future: history.future.slice(0, -1) } : { past: history.past.slice(0, -1), future: [...history.future, html] });
    ownHtml.current = next; onChange(next);
    onSelect(Math.min(index, (readWorkbook(next)?.sheets.length ?? 1) - 1));
  };
  const inRange = (r: number, c: number) => r >= Math.min(active.row, end.row) && r <= Math.max(active.row, end.row) && c >= Math.min(active.col, end.col) && c <= Math.max(active.col, end.col);
  const changeTab = (action: 'add' | 'duplicate' | 'delete') => {
    const next = structuredClone(model);
    if (action === 'delete') {
      if (next.sheets.length === 1 || !window.confirm(`Delete sheet “${next.sheets[index].name}”?`)) return;
      next.sheets.splice(index, 1); onSelect(Math.max(0, index - 1));
    } else {
      next.sheets.push({ ...(action === 'duplicate' ? structuredClone(next.sheets[index]) : { rows: [] }), name: uniqueSheetName(next) });
      onSelect(next.sheets.length - 1);
    }
    publish(next);
  };
  const stats: number[] = [];
  const displayModel = computed?.html === html ? computed.model : model;
  for (let r = Math.min(active.row, end.row); r <= Math.max(active.row, end.row) && r < model.sheets[index].rows.length; r++) {
    for (let c = Math.min(active.col, end.col); c <= Math.max(active.col, end.col) && c < model.sheets[index].rows[r].length; c++) {
      const value = displayModel.sheets[index]?.rows[r]?.[c]; if (typeof value === 'number') stats.push(value);
    }
  }
  return <div className="sheets-grid-editor" onKeyDown={event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z' && !editing && event.target === viewport.current) { event.preventDefault(); undo(event.shiftKey); }
  }}>
    <div className="sheets-grid-toolbar" role="toolbar" aria-label="Spreadsheet tools">
      <button aria-label="Undo" title="Undo (Ctrl/⌘ Z)" disabled={disabled || !history.past.length} onClick={() => undo()}><Undo2 size={16} /></button>
      <button aria-label="Redo" title="Redo (Ctrl/⌘ Shift Z)" disabled={disabled || !history.future.length} onClick={() => undo(true)}><Redo2 size={16} /></button>
      <span className="sheets-grid-divider" />
      <button disabled={disabled} onClick={() => {
        const name = window.prompt('Sheet name', model.sheets[index].name);
        if (name === null) return;
        try { publish(renameSheet(model, index, name)); } catch (error) { setMessage((error as Error).message); }
      }}>Rename sheet</button>
      <button onClick={() => changeTab('duplicate')} disabled={disabled}><Copy size={14} /> Duplicate sheet</button>
      <button onClick={() => changeTab('delete')} disabled={disabled || model.sheets.length <= 1}><Trash2 size={14} /> Delete sheet</button>
      <label><input type="checkbox" checked={showFormulas} onChange={e => setShowFormulas(e.target.checked)} /> Show formulas</label>
    </div>
    <div className="sheets-grid-formula-bar">
      <input aria-label="Go to cell" value={nameBox} onChange={e => setNameBox(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { const p = parseAddress(nameBox); if (p) { navigate(p.row, p.col); viewport.current?.focus(); } else setMessage('Enter a cell address such as A1 or AA25.'); } }} />
      <span aria-hidden="true">ƒx</span>
      <input ref={formulaBar} aria-label="Cell value or formula" value={draft} disabled={disabled} onFocus={() => { cancelBlur.current = false; clearPoint(); setEditSource('bar'); setEditing(true); }} onChange={e => updateDraft(e.target.value)} onBlur={commit} onKeyDown={editKey} placeholder="Enter a value or formula, e.g. =SUM(A1:A10)" />
    </div>
    <div ref={viewport} className="sheets-grid-viewport" role="grid" aria-label={model.sheets[index].name} aria-rowcount={rows + 1} aria-colcount={cols + 1} aria-activedescendant={`sheet-cell-${active.row}-${active.col}`} tabIndex={0}
      onScroll={e => setScroll({ top: e.currentTarget.scrollTop, left: e.currentTarget.scrollLeft })}
      onCopy={e => { if (editing || e.target !== viewport.current) return; e.preventDefault(); e.clipboardData.setData('text/plain', copyRange(model, index, active, end)); }}
      onPaste={e => { if (editing || disabled || e.target !== viewport.current) return; e.preventDefault(); const values = parseClipboard(e.clipboardData.getData('text/plain')); if (values.reduce((n, r) => n + r.length, 0) > 100000) { setMessage('Paste up to 100,000 cells at once.'); return; } publish(patchCells(model, index, active, values)); setEnd({ row: active.row + values.length - 1, col: active.col + Math.max(...values.map(r => r.length)) - 1 }); }}
      onKeyDown={e => {
        if (editing || e.target !== viewport.current) return;
        const p = e.shiftKey ? end : active;
        const moves: Record<string, [number, number]> = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1], Enter: [e.shiftKey ? -1 : 1, 0], Tab: [0, e.shiftKey ? -1 : 1] };
        if (moves[e.key]) { e.preventDefault(); const [r, c] = moves[e.key]; navigate(p.row + r, p.col + c, e.shiftKey && e.key.startsWith('Arrow')); }
        else if ((e.key === 'Delete' || e.key === 'Backspace') && !disabled) {
          e.preventDefault(); e.stopPropagation();
          const start = { row: Math.min(active.row, end.row), col: Math.min(active.col, end.col) };
          const values = Array.from({ length: Math.abs(active.row - end.row) + 1 }, () => Array<Cell>(Math.abs(active.col - end.col) + 1).fill(null));
          publish(patchCells(model, index, start, values));
        } else if (!disabled && (e.key === 'F2' || (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey))) {
          e.preventDefault(); beginEdit(e.key === 'F2' ? String(raw) : e.key);
        }
      }}>
      <div className="sheets-grid-canvas" style={{ width: gutter + horizontal.offset(cols), height: rowHeight + vertical.offset(rows) }}>
        <div className="sheets-grid-corner" style={{ left: scroll.left, top: scroll.top, width: gutter, height: rowHeight }} />
        <div role="row" aria-rowindex={1}>
          {visibleCols.map(c => <div role="columnheader" key={c} className={`sheets-grid-column ${c >= Math.min(active.col, end.col) && c <= Math.max(active.col, end.col) ? 'is-selected' : ''}`} style={{ left: gutter + horizontal.offset(c), top: scroll.top, width: horizontal.size(c), height: rowHeight }}>{columnLabel(c)}{resizeHandle('column_widths', c)}</div>)}
        </div>
        {visibleRows.map(r => <div role="row" aria-rowindex={r + 2} key={r}>
          <div role="rowheader" className={`sheets-grid-row ${r >= Math.min(active.row, end.row) && r <= Math.max(active.row, end.row) ? 'is-selected' : ''}`} style={{ left: scroll.left, top: rowHeight + vertical.offset(r), width: gutter, height: vertical.size(r) }}>{r + 1}{resizeHandle('row_heights', r)}</div>
          {visibleCols.map(c => {
            const value = model.sheets[index].rows[r]?.[c] ?? '';
            const formula = typeof value === 'string' && value.startsWith('=');
            const shown = formula && !showFormulas ? displayModel.sheets[index]?.rows[r]?.[c] ?? value : value;
            const current = r === active.row && c === active.col;
            return <div role="gridcell" aria-colindex={c + 2} aria-selected={inRange(r, c)} aria-label={`${columnLabel(c)}${r + 1}: ${shown}`} id={`sheet-cell-${r}-${c}`} key={c}
              className={`sheets-grid-cell ${inRange(r, c) ? 'is-selected' : ''} ${current ? 'is-active' : ''} ${pointed?.row === r && pointed?.col === c ? 'is-reference' : ''} ${typeof shown === 'number' ? 'is-number' : ''} ${shown === '#ERR' ? 'is-error' : ''}`}
              style={{ left: gutter + horizontal.offset(c), top: rowHeight + vertical.offset(r), width: horizontal.size(c), height: vertical.size(r) }} title={formula ? value : undefined}
              onPointerDown={e => { if (e.target instanceof HTMLInputElement) return; if (editing && draft.startsWith('=')) { e.preventDefault(); pickCell({ row: r, col: c }); return; } if (editing && current) return; e.preventDefault(); select({ row: r, col: c }, e.shiftKey); dragging.current = true; viewport.current?.focus(); }}
              onPointerEnter={() => { if (dragging.current) setEnd({ row: r, col: c }); }}
              onDoubleClick={() => { if (!disabled) { beginEdit(String(value)); } }}>
              {current && editing && editSource === 'cell' ? <input ref={editor} aria-label={`Edit ${address(active)}`} value={draft} onChange={e => updateDraft(e.target.value)} onBlur={commit} onKeyDown={editKey} /> : typeof shown === 'number' ? Number(shown.toPrecision(12)).toLocaleString(undefined, { maximumFractionDigits: 10 }) : String(shown)}
            </div>;
          })}
        </div>)}
      </div>
    </div>
    <div className="sheets-grid-bottom">
      <button className="sheets-grid-add" aria-label="Add sheet" title="Add sheet" onClick={() => changeTab('add')} disabled={disabled}><Plus size={18} /></button>
      <div className="sheets-grid-tabs" role="tablist" aria-label="Workbook sheets">
        {model.sheets.map((sheet, i) => <button type="button" role="tab" aria-selected={i === index} key={sheet.name} className={i === index ? 'is-active' : ''} onClick={() => { if (editing) commit(); onSelect(i); }}>{sheet.name}</button>)}
      </div>
      <output className="sheets-grid-summary">{stats.length ? `Sum: ${stats.reduce((a, b) => a + b, 0).toLocaleString()} · Count: ${stats.length}` : address(active)}</output>
    </div>
    {message && <div className="sheets-grid-message" role="status">{message}</div>}
  </div>;
}
