import test from 'node:test';
import assert from 'node:assert/strict';
import type { KeyboardEvent } from 'react';
import { ontologyTreeKeyDown } from './use-ontology-tree-keyboard';

/** Small DOM fixture; no browser, requests, or workspace access are involved. */
export class TreeElement {
  static focused: TreeElement | null = null;
  parentElement: TreeElement | null = null;
  children: TreeElement[] = [];
  disabled = false;
  scrolled = false;
  clicks = 0;
  onClick?: () => void;
  constructor(public tag = 'button', public attrs: Record<string, string> = {}) {}
  append(...children: TreeElement[]) { for (const child of children) { child.parentElement = this; this.children.push(child); } return this; }
  matches(selector: string): boolean {
    return selector.split(',').some(part => {
      const s = part.trim();
      if (s.startsWith('[contenteditable]')) return this.hasAttribute('contenteditable') && this.attrs.contenteditable !== 'false';
      const attribute = s.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
      return attribute ? this.hasAttribute(attribute[1]) && (attribute[2] === undefined || this.attrs[attribute[1]] === attribute[2]) : this.tag === s;
    });
  }
  closest(selector: string): TreeElement | null { return this.matches(selector) ? this : this.parentElement?.closest(selector) || null; }
  contains(node?: TreeElement | null): boolean { return !!node && (node === this || this.children.some(child => child.contains(node))); }
  querySelectorAll(selector: string): TreeElement[] { return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
  getAttribute(name: string) { return this.attrs[name] ?? null; }
  hasAttribute(name: string) { return name in this.attrs; }
  focus() { TreeElement.focused = this; }
  scrollIntoView() { this.scrolled = true; }
  click() { this.clicks++; this.onClick?.(); }
}
const row = () => new TreeElement('li', { 'data-ontology-tree-row': '' });
const item = (id: string, selectable = true) => new TreeElement('button', { 'data-ontology-tree-item': id, ...(selectable ? { 'data-ontology-tree-select': '' } : {}) });
export function press(root: TreeElement, target: TreeElement, key: string, modifiers: Record<string, boolean> = {}) {
  let prevented = false; let stopped = false;
  ontologyTreeKeyDown({ currentTarget: root, target, key, ...modifiers, preventDefault: () => { prevented = true; }, stopPropagation: () => { stopped = true; } } as unknown as KeyboardEvent<HTMLElement>);
  return { prevented, stopped };
}

test('arrows move through rendered terms, invoke the canvas selection action, and stop at each end', () => {
  const root = new TreeElement('nav'); const a = item('a'); const b = item('b'); const c = item('c');
  const disabled = item('empty', false); disabled.disabled = true;
  const hidden = row().append(item('hidden')); hidden.attrs.hidden = '';
  root.append(row().append(a), row().append(disabled), hidden, row().append(b), row().append(c));
  const selected: string[] = []; for (const button of [a, b, c]) button.onClick = () => selected.push(button.attrs['data-ontology-tree-item']);
  assert.deepEqual(press(root, a, 'ArrowDown'), { prevented: true, stopped: true });
  assert.equal(TreeElement.focused, b); assert.equal(b.scrolled, true); assert.deepEqual(selected, ['b']);
  press(root, b, 'ArrowDown'); press(root, c, 'ArrowDown');
  assert.deepEqual(selected, ['b', 'c']);
  press(root, c, 'ArrowUp'); press(root, b, 'Home'); press(root, a, 'ArrowUp'); press(root, a, 'End');
  assert.deepEqual(selected, ['b', 'c', 'b', 'a', 'c']);
});

test('left/right expand, descend, ascend, and collapse without activating folder navigation', () => {
  const root = new TreeElement('nav'); const branch = row(); const folder = item('folder', false);
  folder.attrs['data-ontology-tree-toggle'] = ''; folder.attrs['aria-expanded'] = 'false';
  const child = item('child'); const childRow = row().append(child); branch.append(folder); root.append(branch);
  folder.onClick = () => {
    const expand = folder.attrs['aria-expanded'] === 'false'; folder.attrs['aria-expanded'] = String(expand);
    if (expand) branch.append(childRow); else { branch.children = [folder]; childRow.parentElement = null; }
  };
  press(root, folder, 'ArrowRight'); assert.equal(folder.clicks, 1); assert.equal(child.clicks, 0);
  press(root, folder, 'ArrowRight'); assert.equal(TreeElement.focused, child); assert.equal(child.clicks, 1);
  press(root, child, 'ArrowLeft'); assert.equal(TreeElement.focused, folder); assert.equal(folder.clicks, 1);
  press(root, folder, 'ArrowLeft'); assert.equal(folder.attrs['aria-expanded'], 'false');
  const end = item('end'); root.append(row().append(end));
  press(root, folder, 'ArrowDown'); assert.equal(TreeElement.focused, end); assert.equal(child.clicks, 1);
});

test('a separate disclosure button navigates from its term row, including multiple inheritance occurrences', () => {
  const root = new TreeElement('nav'); const a = item('parent1/shared'); const b = item('parent2/shared');
  const disclosure = new TreeElement('button', { 'data-ontology-tree-toggle': '', 'aria-expanded': 'true' });
  root.append(row().append(disclosure, a), row().append(b));
  press(root, disclosure, 'ArrowDown'); assert.equal(TreeElement.focused, b); assert.equal(b.clicks, 1);
  press(root, b, 'ArrowUp'); assert.equal(TreeElement.focused, a); assert.equal(a.clicks, 1);
});

test('typing, modified shortcuts, Enter, unrelated controls and other panels keep native behavior', () => {
  const root = new TreeElement('nav'); const a = item('a'); const b = item('b'); root.append(row().append(a), row().append(b));
  for (const tag of ['input', 'textarea', 'select']) {
    const field = new TreeElement(tag); a.parentElement!.append(field); assert.equal(press(root, field, 'ArrowDown').prevented, false);
  }
  const editable = new TreeElement('span', { contenteditable: 'true' }); a.parentElement!.append(editable);
  assert.equal(press(root, editable, 'ArrowDown').prevented, false);
  for (const modifier of ['ctrlKey', 'metaKey', 'altKey', 'shiftKey', 'defaultPrevented']) assert.equal(press(root, a, 'ArrowDown', { [modifier]: true }).prevented, false);
  assert.equal(press(root, a, 'Enter').prevented, false);
  assert.equal(press(root, new TreeElement('input'), 'ArrowDown').prevented, false);
  assert.equal(press(new TreeElement('nav'), a, 'ArrowDown').prevented, false);
  assert.equal(b.clicks, 0);
});
