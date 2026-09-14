'use client';

import React, { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export type SheetsEditorMode = 'preview' | 'code';

type MenuKey = 'file' | 'edit' | 'view' | 'insert' | null;

export type SheetsMenuEntry = {
  id: string;
  label?: string;
  shortcut?: string;
  disabled?: boolean;
  checked?: boolean;
  separator?: boolean;
  items?: SheetsMenuEntry[];
  onSelect?: () => void;
};

function isSeparator(item: SheetsMenuEntry): boolean {
  return Boolean(item.separator);
}

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
}): SheetsMenuEntry[] {
  return [
    { id: 'undo', label: 'Undo', shortcut: `${opts.mod}Z`, disabled: true },
    { id: 'redo', label: 'Redo', shortcut: `${opts.mod}Y`, disabled: true },
    { id: 'sep-history', separator: true },
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
    { id: 'sep-manual-edit', separator: true },
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
}): SheetsMenuEntry[] {
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

function MenuRow({ item, onClose }: { item: SheetsMenuEntry; onClose: () => void }) {
  const [subOpen, setSubOpen] = useState(false);
  if (isSeparator(item)) {
    return <div role="separator" className="my-1 h-px bg-border" />;
  }
  const submenu = item.items?.filter((child) => !isSeparator(child));
  if (submenu?.length) {
    return (
      <div
        className="relative"
        onMouseEnter={() => {
          if (!item.disabled) setSubOpen(true);
        }}
        onMouseLeave={() => setSubOpen(false)}
      >
        <button
          type="button"
          role="menuitem"
          aria-haspopup="menu"
          aria-expanded={subOpen}
          disabled={item.disabled}
          data-testid={`sheets-menuitem-${item.id}`}
          onClick={() => {
            if (item.disabled) return;
            setSubOpen((open) => !open);
          }}
          className={cn(
            'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
            item.disabled
              ? 'cursor-not-allowed text-muted-foreground/50'
              : 'hover:bg-muted',
          )}
        >
          <span className="w-3.5 shrink-0" />
          <span className="flex-1">{item.label}</span>
          <ChevronRight size={12} className="opacity-60" />
        </button>
        {subOpen && !item.disabled ? (
          <div
            role="menu"
            data-testid={`sheets-submenu-${item.id}`}
            className="absolute left-full top-0 z-[301] ml-0.5 min-w-[10rem] rounded-md border border-border bg-card py-1 shadow-lg"
          >
            {submenu.map((child) => (
              <MenuRow key={child.id} item={child} onClose={onClose} />
            ))}
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <button
      key={item.id}
      type="button"
      role="menuitem"
      disabled={item.disabled}
      data-testid={`sheets-menuitem-${item.id}`}
      onClick={() => {
        if (item.disabled || !item.onSelect) return;
        item.onSelect();
        onClose();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
        item.disabled
          ? 'cursor-not-allowed text-muted-foreground/50'
          : 'hover:bg-muted',
      )}
    >
      <span className="w-3.5 shrink-0">
        {item.checked ? <Check size={12} className="text-workspace-accent" /> : null}
      </span>
      <span className="flex-1">{item.label}</span>
      {item.shortcut ? (
        <span className="text-[10px] text-muted-foreground">{item.shortcut}</span>
      ) : null}
    </button>
  );
}

function MenuDropdown({
  label,
  menuKey,
  open,
  onOpenChange,
  items,
}: {
  label: string;
  menuKey: Exclude<MenuKey, null>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: SheetsMenuEntry[];
}) {
  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid={`sheets-menu-${menuKey}`}
        onClick={() => onOpenChange(!open)}
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-2 py-1 text-xs font-medium transition-colors',
          open
            ? 'bg-muted text-foreground'
            : 'text-foreground/90 hover:bg-muted hover:text-foreground',
        )}
      >
        {label}
        <ChevronDown size={12} className="opacity-60" />
      </button>
      {open && (
        <div
          role="menu"
          data-testid={`sheets-menu-${menuKey}-dropdown`}
          className="absolute left-0 top-full z-[300] mt-1 min-w-[12.5rem] rounded-md border border-border bg-card py-1 shadow-lg"
        >
          {items.map((item) => (
            <MenuRow key={item.id} item={item} onClose={() => onOpenChange(false)} />
          ))}
        </div>
      )}
    </div>
  );
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
  /** File → Save to My Drive (MinIO copy). Omit when not on an open workbook. */
  onSaveToMyDrive?: () => void;
  saveToMyDriveDisabled?: boolean;
  /** File → Export to XLSX (server-side, formulas evaluated). */
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
  const [openMenu, setOpenMenu] = useState<MenuKey>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const mod = modKey();

  useEffect(() => {
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenMenu(null);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const fileItems: SheetsMenuEntry[] = [
    {
      id: 'new',
      label: 'New Workbook',
      onSelect: onNewWorkbook,
    },
  ];
  const saveItems: SheetsMenuEntry[] = [];
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
      label: 'Save to My Drive',
      disabled: saveToMyDriveDisabled,
      onSelect: onSaveToMyDrive,
    });
  }
  const exportItems: SheetsMenuEntry[] = [];
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
    fileItems.push({ id: 'sep-save', separator: true }, ...saveItems);
  }
  if (exportItems.length) {
    fileItems.push({ id: 'sep-export', separator: true }, ...exportItems);
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
  });

  const insertItems = buildSheetsInsertMenu({
    canInsert: Boolean(onInsertTab) && !insertTabDisabled,
    canDuplicate: Boolean(onDuplicateTab) && !duplicateTabDisabled,
    onInsertTab: () => onInsertTab?.(),
    onDuplicate: () => onDuplicateTab?.(),
  });

  const canChangeMode = Boolean(mode && onModeChange);
  const viewItems: SheetsMenuEntry[] = [
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
    { id: 'sep-refresh', separator: true },
    {
      id: 'refresh',
      label: 'Refresh',
      shortcut: `${mod}R`,
      disabled: !onRefresh || refreshDisabled,
      onSelect: () => onRefresh?.(),
    },
  ];

  return (
    <div ref={rootRef} className="flex min-w-0 items-center gap-1" data-testid="sheets-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Sheets</span>
      <MenuDropdown
        label="File"
        menuKey="file"
        open={openMenu === 'file'}
        onOpenChange={(open) => setOpenMenu(open ? 'file' : null)}
        items={fileItems}
      />
      <MenuDropdown
        label="Edit"
        menuKey="edit"
        open={openMenu === 'edit'}
        onOpenChange={(open) => setOpenMenu(open ? 'edit' : null)}
        items={editItems}
      />
      <MenuDropdown
        label="View"
        menuKey="view"
        open={openMenu === 'view'}
        onOpenChange={(open) => setOpenMenu(open ? 'view' : null)}
        items={viewItems}
      />
      <MenuDropdown
        label="Insert"
        menuKey="insert"
        open={openMenu === 'insert'}
        onOpenChange={(open) => setOpenMenu(open ? 'insert' : null)}
        items={insertItems}
      />
      {trailing}
    </div>
  );
}
