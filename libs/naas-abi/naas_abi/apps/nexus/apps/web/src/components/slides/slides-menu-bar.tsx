'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export type SlidesEditorMode = 'preview' | 'code';

type MenuKey = 'file' | 'view' | null;

export type SlidesDownloadItem = {
  id: string;
  label: string;
  disabled?: boolean;
  onSelect: () => void;
};

interface MenuItem {
  id: string;
  label: string;
  shortcut?: string;
  disabled?: boolean;
  checked?: boolean;
  onSelect?: () => void;
  submenu?: SlidesDownloadItem[];
}

function MenuDropdown({
  label,
  open,
  onOpenChange,
  items,
}: {
  label: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: MenuItem[];
}) {
  const [openSubmenu, setOpenSubmenu] = useState<string | null>(null);

  useEffect(() => {
    if (!open) setOpenSubmenu(null);
  }, [open]);

  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
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
          className="absolute left-0 top-full z-[300] mt-1 min-w-[14rem] rounded-md border border-border bg-card py-1 shadow-lg"
        >
          {items.map((item) =>
            item.submenu?.length ? (
              <div
                key={item.id}
                className="relative"
                onMouseEnter={() => setOpenSubmenu(item.id)}
                onMouseLeave={() => setOpenSubmenu((current) => (current === item.id ? null : current))}
              >
                <button
                  type="button"
                  role="menuitem"
                  aria-haspopup="menu"
                  aria-expanded={openSubmenu === item.id}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors hover:bg-muted"
                >
                  <span className="w-3.5 shrink-0" />
                  <span className="flex-1">{item.label}</span>
                  <ChevronRight size={12} className="opacity-60" />
                </button>
                {openSubmenu === item.id && (
                  <div
                    role="menu"
                    className="absolute left-full top-0 z-[310] ml-0.5 min-w-[15rem] rounded-md border border-border bg-card py-1 shadow-lg"
                  >
                    {item.submenu.map((sub) => (
                      <button
                        key={sub.id}
                        type="button"
                        role="menuitem"
                        disabled={sub.disabled}
                        onClick={() => {
                          if (sub.disabled) return;
                          sub.onSelect();
                          onOpenChange(false);
                          setOpenSubmenu(null);
                        }}
                        className={cn(
                          'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
                          sub.disabled
                            ? 'cursor-not-allowed text-muted-foreground/50'
                            : 'hover:bg-muted',
                        )}
                      >
                        <span className="w-3.5 shrink-0" />
                        <span className="flex-1">{sub.label}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <button
                key={item.id}
                type="button"
                role="menuitem"
                disabled={item.disabled}
                onClick={() => {
                  if (item.disabled || !item.onSelect) return;
                  item.onSelect();
                  onOpenChange(false);
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
            ),
          )}
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
  /** File → Download submenu (PPTX, PDF, Markdown, …). Omit when not on an open deck. */
  downloadItems?: SlidesDownloadItem[];
  downloadDisabled?: boolean;
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
 * Lean PowerPoint/Google Slides-style menu bar wired to existing Slides actions.
 * Menus: File (with Download flyout), View.
 */
export function SlidesMenuBar({
  onNewPresentation,
  onCommit,
  commitDisabled,
  downloadItems,
  downloadDisabled,
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

  const fileItems: MenuItem[] = [
    {
      id: 'new',
      label: 'New Presentation',
      onSelect: onNewPresentation,
    },
  ];
  if (onCommit) {
    fileItems.push({
      id: 'commit',
      label: 'Save',
      shortcut: `${mod}S`,
      disabled: commitDisabled,
      onSelect: onCommit,
    });
  }
  if (downloadItems?.length) {
    fileItems.push({
      id: 'download',
      label: 'Download',
      submenu: downloadItems.map((item) => ({
        ...item,
        disabled: downloadDisabled || item.disabled,
      })),
    });
  }

  const viewItems: MenuItem[] | null =
    mode && onModeChange
      ? [
          {
            id: 'preview',
            label: 'Preview',
            checked: mode === 'preview',
            onSelect: () => onModeChange('preview'),
          },
          {
            id: 'code',
            label: 'Code',
            checked: mode === 'code',
            onSelect: () => onModeChange('code'),
          },
          ...(onRefresh
            ? [
                {
                  id: 'refresh',
                  label: 'Refresh',
                  shortcut: `${mod}R`,
                  disabled: refreshDisabled,
                  onSelect: onRefresh,
                } satisfies MenuItem,
              ]
            : []),
        ]
      : onRefresh
        ? [
            {
              id: 'refresh',
              label: 'Refresh',
              shortcut: `${mod}R`,
              disabled: refreshDisabled,
              onSelect: onRefresh,
            },
          ]
        : null;

  return (
    <div ref={rootRef} className="flex items-center gap-1">
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Slides</span>
      <MenuDropdown
        label="File"
        open={openMenu === 'file'}
        onOpenChange={(open) => setOpenMenu(open ? 'file' : null)}
        items={fileItems}
      />
      {viewItems && (
        <MenuDropdown
          label="View"
          open={openMenu === 'view'}
          onOpenChange={(open) => setOpenMenu(open ? 'view' : null)}
          items={viewItems}
        />
      )}
      {trailing}
    </div>
  );
}
