'use client';

import type { ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Menu, MenuBar, menuClasses, type MenuEntry } from '@/components/ui/menu';
import {
  DOCUMENT_PARAGRAPH_STYLES,
  type DocumentParagraphStyleId,
  type DocumentsInsertKind,
} from './documents-outline';

export type DocumentsEditorMode = 'preview' | 'code';

export function isDocumentsTypingTarget(target: EventTarget | null): boolean {
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

export function buildSectionsEditMenu(opts: {
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
      label: 'Duplicate page',
      disabled: !opts.canDuplicate,
      onSelect: opts.onDuplicate,
    },
    {
      id: 'delete',
      label: 'Delete page',
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

export function buildSectionsInsertMenu(opts: {
  canInsert: boolean;
  canDuplicate: boolean;
  onInsert: (kind: DocumentsInsertKind) => void;
  onDuplicate: () => void;
}): MenuEntry[] {
  return [
    {
      id: 'page-break',
      label: 'Page break',
      disabled: !opts.canInsert,
      onSelect: () => opts.onInsert('page-break'),
    },
    {
      id: 'heading',
      label: 'Heading',
      disabled: !opts.canInsert,
      onSelect: () => opts.onInsert('heading'),
    },
    {
      id: 'paragraph',
      label: 'Paragraph',
      disabled: !opts.canInsert,
      onSelect: () => opts.onInsert('paragraph'),
    },
    { id: 'sep-dup', kind: 'separator' },
    {
      id: 'duplicate',
      label: 'Duplicate page',
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

export interface DocumentsMenuBarProps {
  /** File → New document */
  onNewPresentation: () => void;
  /** Block a second File → New while create is already in flight. */
  newDisabled?: boolean;
  /** File → Save (git commit under the hood). Omit on index/new pages. */
  onCommit?: () => void;
  commitDisabled?: boolean;
  /** File → Save to My Files (MinIO copy). Omit when not on an open document. */
  onSaveToMyDrive?: () => void;
  saveToMyDriveDisabled?: boolean;
  /** File → Export to PDF. Omit when not on an open document. */
  onExportPdf?: () => void;
  /** File → Export to PDF. Omit when not on an open document. */
  onExportPptx?: () => void;
  /** File → Export HTML. Omit when not on an open document. */
  onExportHtml?: () => void;
  exportDisabled?: boolean;
  /** Edit / Insert page-break and heading. Omit on index/new pages. */
  onInsert?: (kind: DocumentsInsertKind) => void;
  /** @deprecated leftover name; use onInsert */
  onInsertSection?: (kind: DocumentsInsertKind) => void;
  insertSectionDisabled?: boolean;
  onDuplicateSection?: () => void;
  duplicateSectionDisabled?: boolean;
  onDeleteSection?: () => void;
  deleteSectionDisabled?: boolean;
  /** View → Preview / Code / Refresh. Omit on index/new pages. */
  mode?: DocumentsEditorMode;
  onModeChange?: (mode: DocumentsEditorMode) => void;
  /** Edit → Manual edit. Off by default. Omit on index/new pages. */
  manualEdit?: boolean;
  onManualEditChange?: (enabled: boolean) => void;
  manualEditDisabled?: boolean;
  /** View → Refresh (reload document from Forgejo / server). */
  onRefresh?: () => void;
  refreshDisabled?: boolean;
  /** Optional trailing controls (save status). */
  trailing?: ReactNode;
  /** Style picker: Normal text, Title, Subtitle, Heading 1/2/3. No Options item. */
  paragraphStyle?: DocumentParagraphStyleId;
  onParagraphStyleChange?: (style: DocumentParagraphStyleId) => void;
  paragraphStyleDisabled?: boolean;
}

/**
 * Lean document menu bar: File, Edit, View, Insert. All four always
 * render. On pages with no open document yet (index/new) the Edit/View/Insert
 * items are just disabled rather than the menus disappearing, so the bar
 * looks the same on every Documents page.
 * Format / Arrange / Tools stay out of this pass. The style picker is the
 * paragraph-style dropdown (not an Options menu).
 */
export function DocumentsMenuBar({
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
  onInsert,
  onInsertSection,
  insertSectionDisabled,
  onDuplicateSection,
  duplicateSectionDisabled,
  onDeleteSection,
  deleteSectionDisabled,
  mode,
  onModeChange,
  manualEdit = false,
  onManualEditChange,
  manualEditDisabled,
  onRefresh,
  refreshDisabled,
  trailing,
  paragraphStyle = 'normal',
  onParagraphStyleChange,
  paragraphStyleDisabled,
}: DocumentsMenuBarProps) {
  const mod = modKey();

  const fileItems: MenuEntry[] = [
    {
      id: 'new',
      label: 'New document',
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
  if (!onExportPdf && onExportPptx) {
    exportItems.push({
      id: 'export-pdf',
      label: 'Print / Save as PDF',
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
  // document yet) just get that item disabled instead of the whole menu
  // vanishing, so the bar looks identical everywhere in Documents.
  const canToggleManualEdit = Boolean(onManualEditChange) && mode !== 'code';
  const editItems = buildSectionsEditMenu({
    canDuplicate: Boolean(onDuplicateSection) && !duplicateSectionDisabled,
    canDelete: Boolean(onDeleteSection) && !deleteSectionDisabled,
    mod,
    onDuplicate: () => onDuplicateSection?.(),
    onDelete: () => onDeleteSection?.(),
    manualEdit,
    canManualEdit: canToggleManualEdit && !manualEditDisabled,
    onManualEditChange,
  });

  const insertHandler = onInsert || onInsertSection;
  const insertItems = buildSectionsInsertMenu({
    canInsert: Boolean(insertHandler) && !insertSectionDisabled,
    canDuplicate: Boolean(onDuplicateSection) && !duplicateSectionDisabled,
    onInsert: (kind) => insertHandler?.(kind),
    onDuplicate: () => onDuplicateSection?.(),
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
      label="Documents menus"
      title="Documents"
      trailing={trailing}
      testId="documents-menu-bar"
      data-new-disabled={newDisabled ? 'true' : undefined}
    >
      {menus.map(([key, label, items]) => (
        <Menu key={key} label={label} items={items} testId={`sections-menu-${key}`} itemTestIdPrefix="sections-menuitem-" />
      ))}
      <Menu
        testId="documents-style-picker"
        disabled={paragraphStyleDisabled || !onParagraphStyleChange}
        trigger={
          <button type="button" aria-label="Paragraph style" className={cn(menuClasses.trigger, 'min-w-[7.5rem] justify-between')}>
            <span className="truncate">{DOCUMENT_PARAGRAPH_STYLES.find((item) => item.id === paragraphStyle)?.label || 'Normal text'}</span>
            <ChevronDown size={11} className="opacity-60" />
          </button>
        }
        items={DOCUMENT_PARAGRAPH_STYLES.map((item) => ({
          id: item.id,
          label: item.label,
          checked: item.id === paragraphStyle,
          testId: `documents-style-${item.id}`,
          onSelect: () => onParagraphStyleChange?.(item.id),
        }))}
      />
    </MenuBar>
  );
}
