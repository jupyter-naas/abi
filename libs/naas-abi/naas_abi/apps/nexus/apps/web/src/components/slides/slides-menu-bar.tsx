'use client';

import type { ReactNode } from 'react';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';
import { SLIDE_LAYOUTS, type SlideLayout } from './slides-outline';

export type SlidesEditorMode = 'preview' | 'code';

export function isSlidesTypingTarget(target: EventTarget | null): boolean {
  if (target == null || typeof target !== 'object') return false;
  const el = target as {
    tagName?: string;
    isContentEditable?: boolean;
    closest?: (selector: string) => unknown;
  };
  const tag = (el.tagName || '').toUpperCase();
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (el.isContentEditable) return true;
  if (typeof el.closest === 'function') {
    return Boolean(
      el.closest('input, textarea, select, [contenteditable="true"], .monaco-editor'),
    );
  }
  return false;
}

export function buildSlidesEditMenu(opts: {
  canDuplicate: boolean;
  canDelete: boolean;
  mod: string;
  onDuplicate: () => void;
  onDelete: () => void;
  manualEdit?: boolean;
  canManualEdit?: boolean;
  onManualEditChange?: (enabled: boolean) => void;
}): MenuEntry[] {
  return [
    { id: 'undo', label: 'Undo', shortcut: `${opts.mod}Z`, disabled: true },
    { id: 'redo', label: 'Redo', shortcut: `${opts.mod}Y`, disabled: true },
    { id: 'sep-history', kind: 'separator' },
    {
      id: 'duplicate',
      label: 'Duplicate Slide',
      disabled: !opts.canDuplicate,
      onSelect: opts.onDuplicate,
    },
    {
      id: 'delete',
      label: 'Delete Slide',
      shortcut: 'Del',
      disabled: !opts.canDelete,
      onSelect: opts.onDelete,
    },
    { id: 'sep-manual-edit', kind: 'separator' },
    {
      id: 'manual-edit',
      label: 'Manual edit',
      disabled: !opts.canManualEdit,
      checked: Boolean(opts.manualEdit),
      onSelect: () => opts.onManualEditChange?.(!opts.manualEdit),
    },
  ];
}

export function buildSlidesInsertMenu(opts: {
  canInsert: boolean;
  canDuplicate: boolean;
  onInsert: (layout: SlideLayout) => void;
  onDuplicate: () => void;
}): MenuEntry[] {
  return [
    {
      id: 'new-slide',
      kind: 'submenu',
      label: 'New Slide',
      disabled: !opts.canInsert,
      panelTestId: 'slides-submenu-new-slide',
      items: SLIDE_LAYOUTS.map((layout) => ({
        id: `layout-${layout.id}`,
        label: layout.label,
        disabled: !opts.canInsert,
        onSelect: () => opts.onInsert(layout.id),
      })),
    },
    {
      id: 'duplicate',
      label: 'Duplicate Slide',
      disabled: !opts.canDuplicate,
      onSelect: opts.onDuplicate,
    },
  ];
}

function modKey(): string {
  if (typeof navigator !== 'undefined' && /Mac|iPhone|iPad/i.test(navigator.platform)) {
    return '⌘';
  }
  return 'Ctrl+';
}

export interface SlidesMenuBarProps {
  /** File → New Presentation */
  onNewPresentation: () => void;
  /** Block a second File → New while create is already in flight. */
  newDisabled?: boolean;
  /** File → Save (git commit under the hood). Omit on index/new pages. */
  onCommit?: () => void;
  commitDisabled?: boolean;
  /** File → Save to My Files (MinIO copy). Omit when not on an open deck. */
  onSaveToMyDrive?: () => void;
  saveToMyDriveDisabled?: boolean;
  /** File → Export to PDF. Omit when not on an open deck. */
  onExportPdf?: () => void;
  /** File → Export to PPTX. Omit when not on an open deck. */
  onExportPptx?: () => void;
  /** File → Export HTML. Omit when not on an open deck. */
  onExportHtml?: () => void;
  exportDisabled?: boolean;
  /** Edit / Insert slide actions. Omit on index/new pages. */
  onInsertSlide?: (layout: SlideLayout) => void;
  insertSlideDisabled?: boolean;
  onDuplicateSlide?: () => void;
  duplicateSlideDisabled?: boolean;
  onDeleteSlide?: () => void;
  deleteSlideDisabled?: boolean;
  /** View → Preview / Code / Refresh. Omit on index/new pages. */
  mode?: SlidesEditorMode;
  onModeChange?: (mode: SlidesEditorMode) => void;
  /** Edit → Manual edit. Off by default. Omit on index/new pages. */
  manualEdit?: boolean;
  onManualEditChange?: (enabled: boolean) => void;
  manualEditDisabled?: boolean;
  /** View → Refresh (reload deck from Forgejo / server). */
  onRefresh?: () => void;
  refreshDisabled?: boolean;
  /** Optional trailing controls (save status). */
  trailing?: ReactNode;
}

/**
 * Lean PowerPoint-style menu bar: File, Edit, View, Insert. All four always
 * render. On pages with no open deck yet (index/new) the Edit/View/Insert
 * items are just disabled rather than the menus disappearing, so the bar
 * looks the same on every Slides page.
 * Format / Arrange / Tools stay out of this pass.
 */
export function SlidesMenuBar({
  onNewPresentation,
  newDisabled,
  onCommit,
  commitDisabled,
  onSaveToMyDrive,
  saveToMyDriveDisabled,
  onExportPdf,
  onExportPptx,
  onExportHtml,
  exportDisabled,
  onInsertSlide,
  insertSlideDisabled,
  onDuplicateSlide,
  duplicateSlideDisabled,
  onDeleteSlide,
  deleteSlideDisabled,
  mode,
  onModeChange,
  manualEdit = false,
  onManualEditChange,
  manualEditDisabled,
  onRefresh,
  refreshDisabled,
  trailing,
}: SlidesMenuBarProps) {
  const mod = modKey();

  const fileItems: MenuEntry[] = [
    {
      id: 'new',
      label: 'New Presentation',
      disabled: newDisabled,
      onSelect: onNewPresentation,
    },
  ];
  const saveItems: MenuEntry[] = [];
  if (onCommit) {
    saveItems.push({
      id: 'commit',
      label: 'Save',
      shortcut: `${mod}S`,
      disabled: commitDisabled,
      onSelect: onCommit,
    });
  }
  if (onSaveToMyDrive) {
    saveItems.push({
      id: 'save-to-my-drive',
      label: 'Save to My Files',
      disabled: saveToMyDriveDisabled,
      onSelect: onSaveToMyDrive,
    });
  }
  const exportItems: MenuEntry[] = [];
  if (onExportPdf) {
    exportItems.push({
      id: 'export-pdf',
      label: 'Print / Save as PDF',
      disabled: exportDisabled,
      onSelect: onExportPdf,
    });
  }
  if (onExportPptx) {
    exportItems.push({
      id: 'export-pptx',
      label: 'Export to PPTX',
      disabled: exportDisabled,
      onSelect: onExportPptx,
    });
  }
  if (onExportHtml) {
    exportItems.push({
      id: 'export-html',
      label: 'Export HTML',
      disabled: exportDisabled,
      onSelect: onExportHtml,
    });
  }
  if (saveItems.length) {
    fileItems.push({ id: 'sep-save', kind: 'separator' }, ...saveItems);
  }
  if (exportItems.length) {
    fileItems.push({ id: 'sep-export', kind: 'separator' }, ...exportItems);
  }

  // File/Edit/View/Insert are always present, like a real app menu bar :
  // pages that haven't wired a given action (index/new pages have no open
  // deck yet) just get that item disabled instead of the whole menu
  // vanishing, so the bar looks identical everywhere in Slides.
  const canToggleManualEdit = Boolean(onManualEditChange) && mode !== 'code';
  const editItems = buildSlidesEditMenu({
    canDuplicate: Boolean(onDuplicateSlide) && !duplicateSlideDisabled,
    canDelete: Boolean(onDeleteSlide) && !deleteSlideDisabled,
    mod,
    onDuplicate: () => onDuplicateSlide?.(),
    onDelete: () => onDeleteSlide?.(),
    manualEdit,
    canManualEdit: canToggleManualEdit && !manualEditDisabled,
    onManualEditChange,
  });

  const insertItems = buildSlidesInsertMenu({
    canInsert: Boolean(onInsertSlide) && !insertSlideDisabled,
    canDuplicate: Boolean(onDuplicateSlide) && !duplicateSlideDisabled,
    onInsert: (layout) => onInsertSlide?.(layout),
    onDuplicate: () => onDuplicateSlide?.(),
  });

  const canChangeMode = Boolean(mode && onModeChange);
  const viewItems: MenuEntry[] = [
    {
      id: 'preview',
      label: 'Preview',
      disabled: !canChangeMode,
      checked: mode === 'preview',
      onSelect: () => onModeChange?.('preview'),
    },
    {
      id: 'code',
      label: 'Code',
      disabled: !canChangeMode,
      checked: mode === 'code',
      onSelect: () => onModeChange?.('code'),
    },
    { id: 'sep-refresh', kind: 'separator' },
    {
      id: 'refresh',
      label: 'Refresh',
      shortcut: `${mod}R`,
      disabled: !onRefresh || refreshDisabled,
      onSelect: () => onRefresh?.(),
    },
  ];

  const menus: [string, string, MenuEntry[]][] = [
    ['file', 'File', fileItems],
    ['edit', 'Edit', editItems],
    ['view', 'View', viewItems],
    ['insert', 'Insert', insertItems],
  ];

  return (
    <MenuBar
      label="Slides menus"
      title="Slides"
      trailing={trailing}
      testId="slides-menu-bar"
      data-new-disabled={newDisabled ? 'true' : undefined}
    >
      {menus.map(([key, label, items]) => (
        <Menu key={key} label={label} items={items} testId={`slides-menu-${key}`} itemTestIdPrefix="slides-menuitem-" />
      ))}
    </MenuBar>
  );
}
