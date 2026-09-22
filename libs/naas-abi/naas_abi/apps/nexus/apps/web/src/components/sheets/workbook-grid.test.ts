// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import React, { useState } from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot, type Root } from 'react-dom/client';
import { WorkbookGrid } from './workbook-grid';
import { readWorkbook } from './workbook-model';
vi.mock('@/stores/auth', () => ({ authFetch: vi.fn() }));
let root: Root; let host: HTMLDivElement; let saved = '';
function Harness() {
  const [html, setHtml] = useState('<script type="application/vnd.nexus.sheet+json">{"title":"Test","sheets":[{"name":"Sheet1","rows":[[10,"=A1*2"]]}]}</script>');
  const [index, setIndex] = useState(0);
  return React.createElement(WorkbookGrid, { html, workspaceId: '', selectedIndex: index, onSelect: setIndex, onChange: (next: string) => { saved = next; setHtml(next); } });
}
function mount() {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  act(() => root.render(React.createElement(Harness)));
}
function inputValue(input: HTMLInputElement, value: string) {
  act(() => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })); });
  input.setSelectionRange(value.length, value.length);
}
function pointer(el: Element, type: string, x: number, y: number) {
  act(() => el.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y })));
}
function key(el: Element, key: string, extra = {}) { act(() => el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...extra }))); }
afterEach(() => { act(() => root?.unmount()); host?.remove(); });
describe('spreadsheet grid interaction', () => {
  it('renders headers, empty cells and bottom tabs; creates and undoes a sheet', () => {
    mount();
    expect(host.querySelector('[role="columnheader"]')?.textContent).toBe('A');
    expect(host.querySelector('[role="rowheader"]')?.textContent).toBe('1');
    expect(host.querySelectorAll('[role="gridcell"]').length).toBeGreaterThan(100);
    expect(host.querySelector('[role="tab"]')?.textContent).toBe('Sheet1');
    act(() => (host.querySelector('[aria-label="Add sheet"]') as HTMLButtonElement).click());
    expect(readWorkbook(saved)?.sheets).toHaveLength(2);
    expect(host.querySelector('[role="tab"][aria-selected="true"]')?.textContent).toBe('Sheet2');
    act(() => (host.querySelector('[aria-label="Undo"]') as HTMLButtonElement).click());
    expect(readWorkbook(saved)?.sheets).toHaveLength(1);
  });
  it('pastes a range, navigates, deletes a cell and undoes without deleting the tab', () => {
    mount();
    const grid = host.querySelector('[role="grid"]')!;
    const event = new Event('paste', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', { value: { getData: () => '12\t=SUM(A1:A2)\n001\t9' } });
    act(() => grid.dispatchEvent(event));
    expect(readWorkbook(saved)?.sheets[0].rows).toEqual([[12, '=SUM(A1:A2)'], ['001', 9]]);
    key(grid, 'ArrowRight'); key(grid, 'Delete');
    expect(readWorkbook(saved)?.sheets[0].rows[0][1]).toBeNull();
    key(grid, 'z', { ctrlKey: true });
    expect(readWorkbook(saved)?.sheets[0].rows[0][1]).toBe('=SUM(A1:A2)');
    expect(readWorkbook(saved)?.sheets).toHaveLength(1);
  });
  it('escapes a cell edit without changing its value', () => {
    mount(); saved = '';
    key(host.querySelector('[role="grid"]')!, '7');
    const input = host.querySelector('[aria-label="Edit A1"]') as HTMLInputElement;
    expect(input.value).toBe('7');
    key(input, 'Escape');
    expect(saved).toBe('');
    expect(host.querySelector('#sheet-cell-0-0')?.textContent).toBe('10');
  });
  it('enters two numbers and builds the third cell formula with arrows and an operator', () => {
    mount(); const grid = host.querySelector('[role="grid"]')!;
    key(grid, '4'); key(host.querySelector('[aria-label="Edit A1"]')!, 'Tab');
    key(grid, '6'); key(host.querySelector('[aria-label="Edit B1"]')!, 'Tab');
    key(grid, '=');
    const editor = host.querySelector('[aria-label="Edit C1"]') as HTMLInputElement;
    expect(editor.selectionStart).toBe(1);
    key(editor, 'ArrowLeft'); key(editor, 'ArrowLeft');
    expect(editor.value).toBe('=A1');
    inputValue(editor, '=A1+'); key(editor, 'ArrowLeft');
    expect(editor.value).toBe('=A1+B1'); key(editor, 'Enter');
    expect(readWorkbook(saved)?.sheets[0].rows[0]).toEqual([4, 6, '=A1+B1']);
    key(grid, 'z', { ctrlKey: true });
    expect(readWorkbook(saved)?.sheets[0].rows[0]).toEqual([4, 6]);
  });
  it('picks references with the mouse from the formula bar without changing the destination', () => {
    mount(); const grid = host.querySelector('[role="grid"]')!;
    key(grid, 'ArrowRight'); key(grid, 'ArrowRight');
    const bar = host.querySelector('[aria-label="Cell value or formula"]') as HTMLInputElement;
    act(() => bar.focus()); inputValue(bar, '=');
    pointer(host.querySelector('#sheet-cell-0-0')!, 'pointerdown', 0, 0);
    expect(bar.value).toBe('=A1'); inputValue(bar, '=A1+');
    pointer(host.querySelector('#sheet-cell-0-1')!, 'pointerdown', 0, 0);
    expect(bar.value).toBe('=A1+B1'); key(bar, 'Enter');
    expect(readWorkbook(saved)?.sheets[0].rows[0][2]).toBe('=A1+B1');
  });
  it('resizes columns and rows with live layout, persists sizes, and undoes one drag', () => {
    mount();
    const column = host.querySelector('[aria-label="Resize column A"]')!;
    pointer(column, 'pointerdown', 120, 0); pointer(column, 'pointermove', 200, 0);
    expect((host.querySelector('#sheet-cell-0-1') as HTMLElement).style.left).toBe('248px');
    pointer(column, 'pointerup', 200, 0);
    expect(readWorkbook(saved)?.sheets[0].column_widths).toEqual({ 0: 200 });
    const row = host.querySelector('[aria-label="Resize row 1"]')!;
    pointer(row, 'pointerdown', 0, 28); pointer(row, 'pointermove', 0, 60); pointer(row, 'pointerup', 0, 60);
    expect(readWorkbook(saved)?.sheets[0].row_heights).toEqual({ 0: 60 });
    expect((host.querySelector('#sheet-cell-1-0') as HTMLElement).style.top).toBe('88px');
    act(() => (host.querySelector('[aria-label="Undo"]') as HTMLButtonElement).click());
    expect(readWorkbook(saved)?.sheets[0].row_heights).toBeUndefined();
    expect(readWorkbook(saved)?.sheets[0].column_widths).toEqual({ 0: 200 });
  });

});
