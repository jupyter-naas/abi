import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  buildSlidesEditMenu,
  buildSlidesInsertMenu,
  isSlidesTypingTarget,
  SlidesMenuBar,
} from './slides-menu-bar';

describe('buildSlidesEditMenu', () => {
  it('keeps Undo/Redo disabled and groups Duplicate / Delete Slide', () => {
    const items = buildSlidesEditMenu({
      canDuplicate: true,
      canDelete: true,
      mod: '⌘',
      onDuplicate: vi.fn(),
      onDelete: vi.fn(),
    });
    expect(items.map((item) => item.id)).toEqual([
      'undo',
      'redo',
      'sep-history',
      'duplicate',
      'delete',
    ]);
    expect(items[0].disabled).toBe(true);
    expect(items[1].disabled).toBe(true);
    expect(items[3].label).toBe('Duplicate Slide');
    expect(items[4].label).toBe('Delete Slide');
    expect(items[4].shortcut).toBe('Del');
  });

  it('disables Delete Slide on the last slide', () => {
    const items = buildSlidesEditMenu({
      canDuplicate: true,
      canDelete: false,
      mod: 'Ctrl+',
      onDuplicate: vi.fn(),
      onDelete: vi.fn(),
    });
    expect(items.find((item) => item.id === 'delete')?.disabled).toBe(true);
  });
});

describe('buildSlidesInsertMenu', () => {
  it('offers New Slide layouts then Duplicate Slide', () => {
    const onInsert = vi.fn();
    const items = buildSlidesInsertMenu({
      canInsert: true,
      canDuplicate: true,
      onInsert,
      onDuplicate: vi.fn(),
    });
    expect(items[0].label).toBe('New Slide');
    expect(items[0].items?.map((item) => item.label)).toEqual(['Content', 'Cover', 'Section']);
    expect(items[1].label).toBe('Duplicate Slide');
    items[0].items?.[1].onSelect?.();
    expect(onInsert).toHaveBeenCalledWith('cover');
  });
});

describe('isSlidesTypingTarget', () => {
  it('treats inputs and Monaco as typing', () => {
    expect(isSlidesTypingTarget({ tagName: 'INPUT' })).toBe(true);
    expect(isSlidesTypingTarget({ tagName: 'TEXTAREA' })).toBe(true);
    expect(
      isSlidesTypingTarget({
        tagName: 'DIV',
        closest: (selector: string) => selector.includes('.monaco-editor'),
      }),
    ).toBe(true);
    expect(isSlidesTypingTarget({ tagName: 'BUTTON' })).toBe(false);
  });
});

describe('SlidesMenuBar', () => {
  it('shows File Edit View Insert on a deck', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesMenuBar, {
        onNewPresentation: () => {},
        onCommit: () => {},
        onInsertSlide: () => {},
        onDuplicateSlide: () => {},
        onDeleteSlide: () => {},
        mode: 'preview',
        onModeChange: () => {},
        onRefresh: () => {},
      }),
    );
    expect(html).toContain('File');
    expect(html).toContain('Edit');
    expect(html).toContain('View');
    expect(html).toContain('Insert');
    expect(html).toContain('data-testid="slides-menu-edit"');
    expect(html).toContain('data-testid="slides-menu-insert"');
  });

  it('hides Edit and Insert on index-style pages', () => {
    const html = renderToStaticMarkup(
      createElement(SlidesMenuBar, {
        onNewPresentation: () => {},
      }),
    );
    expect(html).toContain('File');
    expect(html).not.toContain('data-testid="slides-menu-edit"');
    expect(html).not.toContain('data-testid="slides-menu-insert"');
    expect(html).not.toContain('data-testid="slides-menu-view"');
  });
});
