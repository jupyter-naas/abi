'use client';

import type { ReactNode } from 'react';
import { Menu, MenuBar, type MenuEntry } from '@/components/ui/menu';

export type SheetsEditorMode = 'preview' | 'code';

export function isSheetsTypingTarget(target: EventTarget | null): boolean {
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

export function buildSheetsEditMenu(opts: {
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
      label: 'Duplicate sheet tab',
      disabled: !opts.canDuplicate,
      onSelect: opts.onDuplicate,
    },
    {
      id: 'delete',
      label: 'Delete sheet tab',
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

export function buildSheetsInsertMenu(opts: {
  canInsert: boolean;
  canDuplicate: boolean;
  onInsertTab: () => void;
  onDuplicate: () => void;
}): MenuEntry[] {
  return [
    {
      id: 'new-tab',
      label: 'New sheet tab',
      disabled: !opts.canInsert,
      onSelect: opts.onInsertTab,
    },
    {
      id: 'duplicate',
      label: 'Duplicate sheet tab',
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

export interface SheetsMenuBarProps {
  /** File → New Workbook */
  onNewWorkbook: () => void;
  /** File → Save (git commit under the hood). Omit on index/new pages. */
  onCommit?: () => void;
  commitDisabled?: boolean;
  /** File → Save to My Files (MinIO copy). Omit when not on an open workbook. */
  onSaveToMyDrive?: () => void;
  saveToMyDriveDisabled?: boolean;
  /** File → Export to XLSX (server-side; formula strings preserved). */
  onExportXlsx?: () => void;
  /** File → Export HTML. Omit when not on an open workbook. */
  onExportHtml?: () => void;
  exportDisabled?: boolean;
  /** Edit / Insert tab actions. Omit on index/new pages. */
  onInsertTab?: () => void;
  insertTabDisabled?: boolean;
  onDuplicateTab?: () => void;
  duplicateTabDisabled?: boolean;
  onDeleteTab?: () => void;
  deleteTabDisabled?: boolean;
  /** View → Preview / Code / Refresh. Omit on index/new pages. */
  mode?: SheetsEditorMode;
  onModeChange?: (mode: SheetsEditorMode) => void;
  /** Edit → Manual edit. Off by default. Omit on index/new pages. */
  manualEdit?: boolean;
  onManualEditChange?: (enabled: boolean) => void;
  manualEditDisabled?: boolean;
  /** View → Refresh (reload workbook from Forgejo / server). */
  onRefresh?: () => void;
  refreshDisabled?: boolean;
  /** Optional trailing controls (save status). */
  trailing?: ReactNode;
}

/**
 * Spreadsheet-style menu bar: File, Edit, View, Insert. All four always
 * render. On pages with no open workbook yet (index/new) the Edit/View/Insert
 * items are just disabled rather than the menus disappearing, so the bar
 * looks the same on every Sheets page.
 */
export function SheetsMenuBar({
  onNewWorkbook,
  onCommit,
  commitDisabled,
  onSaveToMyDrive,
  saveToMyDriveDisabled,
  onExportXlsx,
  onExportHtml,
  exportDisabled,
  onInsertTab,
  insertTabDisabled,
  onDuplicateTab,
  duplicateTabDisabled,
  onDeleteTab,
  deleteTabDisabled,
  mode,
  onModeChange,
  manualEdit = false,
  onManualEditChange,
  manualEditDisabled,
  onRefresh,
  refreshDisabled,
  trailing,
}: SheetsMenuBarProps) {
  const mod = modKey();

  const fileItems: MenuEntry[] = [
    {
      id: 'new',
      label: 'New Workbook',
      onSelect: onNewWorkbook,
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
  if (onExportXlsx) {
    exportItems.push({
      id: 'export-xlsx',
      label: 'Export to Excel (XLSX)',
      disabled: exportDisabled,
      onSelect: onExportXlsx,
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
  // workbook yet) just get that item disabled instead of the whole menu
  // vanishing, so the bar looks identical everywhere in Sheets.
  const canToggleManualEdit = Boolean(onManualEditChange) && mode !== 'code';
  const editItems = buildSheetsEditMenu({
    canDuplicate: Boolean(onDuplicateTab) && !duplicateTabDisabled,
    canDelete: Boolean(onDeleteTab) && !deleteTabDisabled,
    mod,
    onDuplicate: () => onDuplicateTab?.(),
    onDelete: () => onDeleteTab?.(),
    manualEdit,
    canManualEdit: canToggleManualEdit && !manualEditDisabled,
    onManualEditChange,
  }).filter(item => Boolean(onManualEditChange) || !['manual-edit', 'sep-manual-edit'].includes(item.id));

  const insertItems = buildSheetsInsertMenu({
    canInsert: Boolean(onInsertTab) && !insertTabDisabled,
    canDuplicate: Boolean(onDuplicateTab) && !duplicateTabDisabled,
    onInsertTab: () => onInsertTab?.(),
    onDuplicate: () => onDuplicateTab?.(),
  });

  const canChangeMode = Boolean(mode && onModeChange);
  const viewItems: MenuEntry[] = [
    {
      id: 'preview',
      label: 'Spreadsheet',
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
      label="Sheets menus"
      title="Sheets"
      trailing={trailing}
      testId="sheets-menu-bar"
    >
      {menus.map(([key, label, items]) => (
        <Menu key={key} label={label} items={items} testId={`sheets-menu-${key}`} itemTestIdPrefix="sheets-menuitem-" />
      ))}
    </MenuBar>
  );
}
