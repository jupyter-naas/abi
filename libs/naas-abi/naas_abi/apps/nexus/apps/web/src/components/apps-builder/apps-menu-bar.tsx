'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

type MenuKey = 'file' | 'edit' | null;

export type AppsMenuEntry = {
  id: string;
  label?: string;
  shortcut?: string;
  disabled?: boolean;
  separator?: boolean;
  /** Group caption — renders as a non-interactive row, not a menu item. */
  heading?: boolean;
  /** Ticks the row: which app the Edit menu is currently pointing at. */
  checked?: boolean;
  title?: string;
  onSelect?: () => void;
};

function MenuRow({ item, onClose }: { item: AppsMenuEntry; onClose: () => void }) {
  if (item.separator) {
    return <div role="separator" className="my-1 h-px bg-border" />;
  }
  if (item.heading) {
    return (
      <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {item.label}
      </p>
    );
  }
  return (
    <button
      type="button"
      role="menuitem"
      disabled={item.disabled}
      title={item.title}
      data-testid={`apps-menuitem-${item.id}`}
      onClick={() => {
        if (item.disabled || !item.onSelect) return;
        item.onSelect();
        onClose();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors',
        item.disabled ? 'cursor-not-allowed text-muted-foreground/50' : 'hover:bg-muted',
      )}
    >
      <span className="w-3.5 shrink-0">
        {item.checked ? <Check size={12} className="text-workspace-accent" /> : null}
      </span>
      <span className="flex-1 truncate">{item.label}</span>
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
  disabled,
  title,
}: {
  label: string;
  menuKey: Exclude<MenuKey, null>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: AppsMenuEntry[];
  /** Drawn greyed and inert — the menu stays on the bar, it just will not open. */
  disabled?: boolean;
  title?: string;
}) {
  return (
    <div className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-disabled={disabled || undefined}
        disabled={disabled}
        title={title}
        data-testid={`apps-menu-${menuKey}`}
        onClick={() => onOpenChange(!open)}
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-2 py-1 text-xs font-medium transition-colors',
          disabled
            ? 'cursor-not-allowed text-muted-foreground/50'
            : open
              ? 'bg-muted text-foreground'
              : 'text-foreground/90 hover:bg-muted hover:text-foreground',
        )}
      >
        {label}
        <ChevronDown size={12} className="opacity-60" />
      </button>
      {open && !disabled && (
        <div
          role="menu"
          data-testid={`apps-menu-${menuKey}-dropdown`}
          className="absolute left-0 top-full z-[300] mt-1 max-h-[70vh] min-w-[12.5rem] max-w-[20rem] overflow-y-auto rounded-md border border-border bg-card py-1 shadow-lg"
        >
          {items.map((item) => (
            <MenuRow key={item.id} item={item} onClose={() => onOpenChange(false)} />
          ))}
        </div>
      )}
    </div>
  );
}

export interface AppsMenuBarProps {
  /** File → New App. Omitted or disabled, the item greys out rather than vanishing. */
  onNewApp?: () => void;
  newAppDisabled?: boolean;
  /** Extra File entries appended under a separator (the open app adds "All apps"). */
  fileExtras?: AppsMenuEntry[];
  /** Entries for an Edit menu. Omitted or empty, no Edit menu is drawn. */
  editItems?: AppsMenuEntry[];
  /** Keep Edit on the bar but inert — the section still reads the same. */
  editDisabled?: boolean;
  editDisabledTitle?: string;
  /** Rendered ahead of the "Apps" label — the editor's back arrow. */
  leading?: ReactNode;
  /** Rendered after the menus: status text, branch name, unsaved marker. */
  trailing?: ReactNode;
}

/**
 * The Apps section's app menu bar, sitting in the topnav through
 * `Header nav=`. Same shape as `SlidesMenuBar` / `DocumentsMenuBar` /
 * the Ontology bar: a section label, then File — so creating an app is a
 * menu entry like every other section's "New …", not a coloured button
 * floating in the top-right corner.
 */
export function AppsMenuBar({
  onNewApp,
  newAppDisabled,
  fileExtras,
  editItems,
  editDisabled,
  editDisabledTitle,
  leading,
  trailing,
}: AppsMenuBarProps) {
  const [openMenu, setOpenMenu] = useState<MenuKey>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpenMenu(null);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenMenu(null);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  const fileItems: AppsMenuEntry[] = [
    {
      id: 'new',
      label: 'New App',
      disabled: !onNewApp || newAppDisabled,
      onSelect: () => onNewApp?.(),
    },
    ...(fileExtras?.length ? [{ id: 'sep-extras', separator: true }, ...fileExtras] : []),
  ];

  return (
    <div
      ref={rootRef}
      className="flex min-w-0 flex-wrap items-center gap-1"
      data-testid="apps-menu-bar"
    >
      {leading}
      <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">Apps</span>
      <MenuDropdown
        label="File"
        menuKey="file"
        open={openMenu === 'file'}
        onOpenChange={(open) => setOpenMenu(open ? 'file' : null)}
        items={fileItems}
      />
      {editItems?.length || editDisabled ? (
        <MenuDropdown
          label="Edit"
          menuKey="edit"
          open={openMenu === 'edit'}
          onOpenChange={(open) => setOpenMenu(open ? 'edit' : null)}
          items={editItems ?? []}
          disabled={editDisabled}
          title={editDisabled ? editDisabledTitle : undefined}
        />
      ) : null}
      {trailing}
    </div>
  );
}
