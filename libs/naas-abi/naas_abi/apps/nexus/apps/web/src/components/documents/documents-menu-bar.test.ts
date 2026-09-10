import { describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  buildSectionsEditMenu,
  buildSectionsInsertMenu,
  isDocumentsTypingTarget,
  DocumentsMenuBar,
} from './documents-menu-bar';

describe('buildSectionsEditMenu', () => {
  it('keeps Undo/Redo disabled and groups Duplicate / Delete Section', () => {
    const items = buildSectionsEditMenu({
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
      'sep-manual-edit',
      'manual-edit',
    ]);
    expect(items[0].disabled).toBe(true);
    expect(items[1].disabled).toBe(true);
    expect(items[3].label).toBe('Duplicate Section');
    expect(items[4].label).toBe('Delete Section');
    expect(items[4].shortcut).toBe('Del');
    expect(items[6].label).toBe('Manual edit');
    expect(items[6].checked).toBe(false);
    expect(items[6].disabled).toBe(true);
  });

  it('checks Manual edit when on and toggles on click', () => {
    const onManualEditChange = vi.fn();
    const on = buildSectionsEditMenu({
      canDuplicate: true,
      canDelete: true,
      mod: '⌘',
      onDuplicate: vi.fn(),
      onDelete: vi.fn(),
      manualEdit: true,
      canManualEdit: true,
      onManualEditChange,
    });
    const item = on.find((entry) => entry.id === 'manual-edit');
    expect(item?.checked).toBe(true);
    expect(item?.disabled).toBe(false);
    item?.onSelect?.();
    expect(onManualEditChange).toHaveBeenCalledWith(false);

    const off = buildSectionsEditMenu({
      canDuplicate: true,
      canDelete: true,
      mod: '⌘',
      onDuplicate: vi.fn(),
      onDelete: vi.fn(),
      manualEdit: false,
      canManualEdit: true,
      onManualEditChange,
    });
    off.find((entry) => entry.id === 'manual-edit')?.onSelect?.();
    expect(onManualEditChange).toHaveBeenCalledWith(true);
  });

  it('disables Delete Section on the last section', () => {
    const items = buildSectionsEditMenu({
      canDuplicate: true,
      canDelete: false,
      mod: 'Ctrl+',
      onDuplicate: vi.fn(),
      onDelete: vi.fn(),
    });
    expect(items.find((item) => item.id === 'delete')?.disabled).toBe(true);
  });
});

describe('buildSectionsInsertMenu', () => {
  it('offers New Section layouts then Duplicate Section', () => {
    const onInsert = vi.fn();
    const items = buildSectionsInsertMenu({
      canInsert: true,
      canDuplicate: true,
      onInsert,
      onDuplicate: vi.fn(),
    });
    expect(items[0].label).toBe('New Section');
    expect(items[0].items?.map((item) => item.label)).toEqual(['Content', 'Cover', 'Section']);
    expect(items[1].label).toBe('Duplicate Section');
    items[0].items?.[1].onSelect?.();
    expect(onInsert).toHaveBeenCalledWith('cover');
  });
});

describe('isDocumentsTypingTarget', () => {
  it('treats inputs and Monaco as typing', () => {
    expect(isDocumentsTypingTarget({ tagName: 'INPUT' })).toBe(true);
    expect(isDocumentsTypingTarget({ tagName: 'TEXTAREA' })).toBe(true);
    expect(
      isDocumentsTypingTarget({
        tagName: 'DIV',
        closest: (selector: string) => selector.includes('.monaco-editor'),
      }),
    ).toBe(true);
    expect(isDocumentsTypingTarget({ tagName: 'BUTTON' })).toBe(false);
  });
});

describe('DocumentsMenuBar', () => {
  it('shows File Edit View Insert on a document', () => {
    const html = renderToStaticMarkup(
      createElement(DocumentsMenuBar, {
        onNewPresentation: () => {},
        onCommit: () => {},
        onInsertSection: () => {},
        onDuplicateSection: () => {},
        onDeleteSection: () => {},
        mode: 'preview',
        onModeChange: () => {},
        onRefresh: () => {},
      }),
    );
    expect(html).toContain('File');
    expect(html).toContain('Edit');
    expect(html).toContain('View');
    expect(html).toContain('Insert');
    expect(html).toContain('data-testid="sections-menu-edit"');
    expect(html).toContain('data-testid="sections-menu-insert"');
    expect(html).not.toContain('data-testid="sections-manual-edit-toggle"');
  });

  it('still shows Edit, View and Insert (disabled) on index-style pages', () => {
    const html = renderToStaticMarkup(
      createElement(DocumentsMenuBar, {
        onNewPresentation: () => {},
      }),
    );
    expect(html).toContain('File');
    expect(html).toContain('data-testid="sections-menu-edit"');
    expect(html).toContain('data-testid="sections-menu-insert"');
    expect(html).toContain('data-testid="sections-menu-view"');
  });
});
