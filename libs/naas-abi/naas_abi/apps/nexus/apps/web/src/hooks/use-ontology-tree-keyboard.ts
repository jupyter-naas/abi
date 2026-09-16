'use client';

import { useLayoutEffect, useRef, type FocusEvent, type KeyboardEvent } from 'react';
import './ontology-tree-keyboard.css';

const ROW = '[data-ontology-tree-row]';
const ITEM = '[data-ontology-tree-item]';
const TOGGLE = '[data-ontology-tree-toggle]';

function ownedButton(row: Element, selector: string): HTMLButtonElement | undefined {
  if (row.matches(selector)) return row as HTMLButtonElement;
  return Array.from(row.querySelectorAll<HTMLButtonElement>(selector)).find(button => button.closest(ROW) === row);
}

/** Arrow selection uses the same click action as the pointer, including canvas updates. */
export function ontologyTreeKeyDown(event: KeyboardEvent<HTMLElement>) {
  if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const target = event.target as HTMLElement;
  if (target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return;
  const root = event.currentTarget;
  const row = target.closest(ROW);
  if (!row || !root.contains(row)) return;
  const current = ownedButton(row, ITEM);
  if (!current || current.disabled) return;
  // Collapsed branches are unmounted by the renderers; disabled/hidden groups are skipped.
  const items = Array.from(root.querySelectorAll<HTMLButtonElement>(ITEM))
    .filter(button => !button.disabled && !button.closest('[hidden], [aria-hidden="true"]'));
  const index = items.indexOf(current);
  if (index < 0) return;
  event.preventDefault();
  event.stopPropagation();
  function select(button: HTMLButtonElement | undefined) {
    if (!button || button === current) return;
    button.focus({ preventScroll: true });
    button.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (button.hasAttribute('data-ontology-tree-select')) button.click();
  }
  if (event.key === 'ArrowDown') { select(items[Math.min(index + 1, items.length - 1)]); return; }
  if (event.key === 'ArrowUp') { select(items[Math.max(index - 1, 0)]); return; }
  if (event.key === 'Home') { select(items[0]); return; }
  if (event.key === 'End') { select(items[items.length - 1]); return; }
  const toggle = ownedButton(row, TOGGLE);
  if (event.key === 'ArrowRight') {
    if (toggle?.getAttribute('aria-expanded') === 'false') { current.focus({ preventScroll: true }); toggle.click(); }
    else if (items[index + 1] && row.contains(items[index + 1])) select(items[index + 1]);
  } else if (toggle?.getAttribute('aria-expanded') === 'true') {
    current.focus({ preventScroll: true }); toggle.click();
  } else {
    const parent = row.parentElement?.closest(ROW);
    if (parent && root.contains(parent)) select(ownedButton(parent, ITEM));
  }
}

/** Keep keyboard focus through route-driven canvas updates without stealing it from other controls. */
export function useOntologyTreeKeyboard() {
  const ref = useRef<HTMLElement>(null);
  const focused = useRef<{ element: HTMLElement; key: string } | null>(null);
  useLayoutEffect(() => {
    const previous = focused.current;
    if (!previous || previous.element.isConnected || !ref.current || document.activeElement !== document.body) return;
    const next = Array.from(ref.current.querySelectorAll<HTMLButtonElement>(ITEM))
      .find(button => button.getAttribute('data-ontology-tree-item') === previous.key && !button.disabled);
    next?.focus({ preventScroll: true });
  });
  return {
    ref,
    onKeyDown: ontologyTreeKeyDown,
    onFocusCapture: (event: FocusEvent<HTMLElement>) => {
      const element = event.target as HTMLElement;
      const row = element.closest(ROW);
      const item = row && ownedButton(row, ITEM);
      if (item) focused.current = { element, key: item.getAttribute('data-ontology-tree-item')! };
    },
    'aria-keyshortcuts': 'ArrowUp ArrowDown ArrowLeft ArrowRight Home End',
  };
}
