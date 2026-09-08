/**
 * New Slides has to be the same control as New Chat, plus a template picker.
 *
 * "Same" is checked by class, not by eye: both render `.sidebar-new-item`, so
 * a future edit to the New Chat styling moves New Slides with it. The picker
 * is checked for menu semantics, because a div-based popup would leave the
 * templates unreachable from the keyboard.
 */

import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { SidebarNewItem, type SidebarNewItemMenuOption } from './sidebar-new-item';

const templates: SidebarNewItemMenuOption[] = [
  { id: 'minimal-light-v1', label: 'Minimal Light', swatch: '#0072ce', onSelect: () => {} },
  { id: 'pitch-dark-v1', label: 'Pitch Dark', swatch: '#111111', onSelect: () => {} },
];

function markup(props: Record<string, unknown> = {}): string {
  return renderToStaticMarkup(
    createElement(SidebarNewItem, {
      label: 'New Slides',
      onClick: () => {},
      menuLabel: 'Choose a template',
      menuOptions: templates,
      menuOpen: false,
      onMenuOpenChange: () => {},
      ...props,
    } as never),
  );
}

describe('SidebarNewItem', () => {
  it('is styled from the same rule as the New Chat launcher', () => {
    expect(markup()).toContain('class="sidebar-new-item"');
  });

  it('shows the label', () => {
    expect(markup()).toContain('New Slides');
  });

  it('is a real button, not a clickable div', () => {
    expect(markup()).toContain('<button type="button"');
  });

  it('carries the active modifier the New Chat launcher uses', () => {
    expect(markup({ active: true })).toContain('sidebar-new-item is-active');
  });

  it('grows its hit area on the mobile panel like New Chat does', () => {
    expect(markup({ mobilePanel: true })).toContain('sidebar-new-item is-mobile-panel');
  });
});

describe('SidebarNewItem template picker', () => {
  it('announces a collapsed menu on the caret', () => {
    const html = markup();
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-label="Choose a template"');
  });

  it('keeps the templates out of the DOM while closed', () => {
    const html = markup();
    expect(html).not.toContain('Minimal Light');
    expect(html).not.toContain('role="menu"');
  });

  it('lists every template as a menu item when open', () => {
    const html = markup({ menuOpen: true });
    expect(html).toContain('role="menu"');
    expect(html).toContain('aria-expanded="true"');
    expect((html.match(/role="menuitem"/g) ?? []).length).toBe(2);
    expect(html).toContain('Minimal Light');
    expect(html).toContain('Pitch Dark');
  });

  it('prefixes an option with the namespace it was given', () => {
    const html = markup({
      menuOpen: true,
      menuOptions: [
        { id: 'one/first-v1', label: 'First', prefix: 'one', onSelect: () => {} },
        { id: 'two/second-v1', label: 'Second', prefix: 'two', onSelect: () => {} },
      ],
    });
    expect(html).toContain('one/');
    expect(html).toContain('two/');
    expect(html).toContain('First');
    expect(html).toContain('Second');
  });

  it('renders no prefix when an option carries none', () => {
    const html = markup({
      menuOpen: true,
      menuOptions: [{ id: 'one/first-v1', label: 'First', onSelect: () => {} }],
    });
    expect(html).toContain('First');
    expect(html).not.toContain('one/');
  });

  it('renders a heading as a label, not a menu item', () => {
    const html = markup({
      menuOpen: true,
      menuOptions: [
        { id: 'heading:abi', label: 'ABI', heading: true },
        { id: 'abi/minimal-light-v1', label: 'Minimal Light', onSelect: () => {} },
      ],
    });
    expect(html).toContain('ABI');
    expect(html).toContain('Minimal Light');
    expect((html.match(/role="menuitem"/g) ?? []).length).toBe(1);
    expect(html).not.toContain('abi/');
  });

  it('says so when no template came back from the server', () => {
    const html = markup({ menuOpen: true, menuOptions: [] });
    expect(html).toContain('No templates loaded');
    expect(html).not.toContain('role="menuitem"');
  });

  it('renders no caret at all without a menu', () => {
    const html = markup({ menuLabel: undefined, onMenuOpenChange: undefined });
    expect(html).not.toContain('aria-haspopup');
    expect(html).toContain('sidebar-new-item');
  });

  it('creates the deck on the main action and only opens the menu on the caret', () => {
    const onClick = vi.fn();
    const onMenuOpenChange = vi.fn();
    // The main action and the caret must be two separate buttons, otherwise
    // clicking "New Slides" would only open a menu and never create a deck.
    const html = markup({ onClick, onMenuOpenChange });
    expect((html.match(/<button type="button"/g) ?? []).length).toBe(2);
  });
});
