'use client';

import React, { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SLIDE_LAYOUTS, type SlideLayout } from './slides-outline';

export type SlidesEditorMode = 'preview' | 'code';

type MenuKey = 'file' | 'edit' | 'view' | 'insert' | null;

export type SlidesMenuEntry = {
  id: string;
  label?: string;
  shortcut?: string;
  disabled?: boolean;
  checked?: boolean;
  separator?: boolean;
  items?: SlidesMenuEntry[];
  onSelect?: () => void;
};

function isSeparator(item: SlidesMenuEntry): boolean {
  return Boolean(item.separator);
}

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
}): SlidesMenuEntry[] {
  return [
    { id: 'undo', label: 'Undo', shortcut: `${opts.mod}Z`, disabled: true },
    { id: 'redo', label: 'Redo', shortcut: `${opts.mod}Y`, disabled: true },
    { id: 'sep-history', separator: true },
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
  ];
}

export function buildSlidesInsertMenu(opts: {
  canInsert: boolean;
  canDuplicate: boolean;
  onInsert: (layout: SlideLayout) => void;
  onDuplicate: () => void;
}): SlidesMenuEntry[] {
  return [
    {
      id: 'new-slide',
      label: 'New Slide',
      disabled: !opts.canInsert,
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

function MenuRow({ item, onClose }: { item: SlidesMenuEntry; onClose: () => void }) {
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
          data-testid={`slides-menuitem-${item.id}`}
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
            data-testid={`slides-submenu-${item.id}`}
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
      data-testid={`slides-menuitem-${item.id}`}
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
  items: SlidesMenuEntry[];
}) {
  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid={`slides-menu-${menuKey}`}
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
          data-testid={`slides-menu-${menuKey}-dropdown`}
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

export interface SlidesMenuBarProps {
  /** File → New Presentation */
  onNewPresentation: () => void;
  /** File → Save (git commit under the hood). Omit on index/new pages. */
  onCommit?: () => void;
  commitDisabled?: boolean;
  /** File → Save to My Drive (MinIO copy). Omit when not on an open deck. */
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
  /** View → Refresh (reload deck from Forgejo / server). */
  onRefresh?: () => void;
  refreshDisabled?: boolean;
  /** Optional trailing controls (save status). */
  trailing?: ReactNode;
}

/**
 * Lean PowerPoint-style menu bar: File, Edit, View, Insert. All four always
 * render — on pages with no open deck yet (index/new) the Edit/View/Insert
 * items are just disabled rather than the menus disappearing, so the bar
 * looks the same on every Slides page.
 * Format / Arrange / Tools stay out of this pass.
 */
export function SlidesMenuBar({
  onNewPresentation,
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
  onRefresh,
  refreshDisabled,
  trailing,
}: SlidesMenuBarProps) {
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

  const fileItems: SlidesMenuEntry[] = [
    {
      id: 'new',
      label: 'New Presentation',
      onSelect: onNewPresentation,
    },
  ];
  const saveItems: SlidesMenuEntry[] = [];
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
  const exportItems: SlidesMenuEntry[] = [];
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
    fileItems.push({ id: 'sep-save', separator: true }, ...saveItems);
  }
  if (exportItems.length) {
    fileItems.push({ id: 'sep-export', separator: true }, ...exportItems);
  }

  // File/Edit/View/Insert are always present, like a real app menu bar —
  // pages that haven't wired a given action (index/new pages have no open
  // deck yet) just get that item disabled instead of the whole menu
  // vanishing, so the bar looks identical everywhere in Slides.
  const editItems = buildSlidesEditMenu({
    canDuplicate: Boolean(onDuplicateSlide) && !duplicateSlideDisabled,
    canDelete: Boolean(onDeleteSlide) && !deleteSlideDisabled,
    mod,
    onDuplicate: () => onDuplicateSlide?.(),
    onDelete: () => onDeleteSlide?.(),
  });

  const insertItems = buildSlidesInsertMenu({
    canInsert: Boolean(onInsertSlide) && !insertSlideDisabled,
    canDuplicate: Boolean(onDuplicateSlide) && !duplicateSlideDisabled,
    onInsert: (layout) => onInsertSlide?.(layout),
    onDuplicate: () => onDuplicateSlide?.(),
  });

  const canChangeMode = Boolean(mode && onModeChange);
  const viewItems: SlidesMenuEntry[] = [
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
    <div ref={rootRef} className="flex min-w-0 items-center gap-1" data-testid="slides-menu-bar">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Slides</span>
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
