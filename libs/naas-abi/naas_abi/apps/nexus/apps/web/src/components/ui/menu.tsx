'use client';

import type { ComponentPropsWithoutRef, ReactNode } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * The one menu style: app menu bars (File / Edit / View), overflow (⋯) menus, row context
 * menus. Built on Radix DropdownMenu for focus, typeahead and Escape. Highlight is grey
 * `bg-muted` under the cursor or keyboard focus, and on a trigger while its menu is open.
 * A disabled row stays under the pointer so its `title` still says why.
 */
export const menuClasses = {
  /** A menu item, radio item, checkbox item or sub-trigger. */
  row: 'flex cursor-default select-none items-center gap-2 px-3 py-1.5 text-xs outline-none transition-colors ![border-radius:0] data-[highlighted]:bg-muted data-[state=open]:bg-muted data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50',
  /** The dropdown / sub-menu panel. */
  surface:
    'z-[300] max-h-[70vh] min-w-[190px] overflow-y-auto border border-border bg-card p-1 text-foreground shadow-lg outline-none ![border-radius:0]',
  /** The File / Edit / View button on a menu bar. */
  trigger:
    'flex items-center gap-1 rounded border-0 bg-transparent px-2 py-1 text-xs font-medium text-foreground/90 shadow-none outline-none ring-0 transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus-visible:bg-muted data-[state=open]:bg-muted data-[state=open]:text-foreground disabled:cursor-not-allowed disabled:text-muted-foreground/50 disabled:hover:bg-transparent',
  separator: 'my-1 h-px bg-border',
  heading: 'px-3 py-1 text-micro font-semibold uppercase tracking-wide text-muted-foreground',
  /** A line of explanation inside a panel (why the rows above are greyed). */
  note: 'max-w-[220px] px-3 py-1 text-xs text-muted-foreground',
  shortcut: 'ml-auto pl-4 text-micro text-muted-foreground',
} as const;

/** One line of a menu, as data. */
export type MenuEntry =
  | { kind?: 'item'; id: string; label: ReactNode; icon?: ReactNode; shortcut?: string; disabled?: boolean;
      /** Ticks the row (the current choice). `undefined` leaves no tick column. */
      checked?: boolean; destructive?: boolean; title?: string; onSelect?: () => void; testId?: string;
      /** Selecting it leaves the menu open (e.g. it opens a modal that owns focus). */
      keepOpen?: boolean }
  | { kind: 'separator'; id: string }
  | { kind: 'heading'; id: string; label: ReactNode }
  | { kind: 'note'; id: string; label: ReactNode }
  | { kind: 'submenu'; id: string; label: ReactNode; icon?: ReactNode; disabled?: boolean; items: MenuEntry[];
      /** The current choice inside, shown at the right of the row (Spacing   Compact ›). */
      value?: ReactNode; testId?: string; panelTestId?: string };

function hasTicks(items: MenuEntry[]): boolean {
  return items.some((item) => (item.kind ?? 'item') === 'item' && 'checked' in item && item.checked !== undefined);
}

/**
 * The rows of a menu panel, from data. `itemTestIdPrefix` names every row and sub-menu
 * trigger without a `testId` of its own: `${itemTestIdPrefix}${id}`.
 */
export function MenuItems({ items, itemTestIdPrefix }: { items: MenuEntry[]; itemTestIdPrefix?: string }) {
  const ticks = hasTicks(items);
  const testIdOf = (item: { id: string; testId?: string }) =>
    item.testId ?? (itemTestIdPrefix ? `${itemTestIdPrefix}${item.id}` : undefined);
  return (
    <>
      {items.map((item) => {
        if (item.kind === 'separator') return <DropdownMenu.Separator key={item.id} className={menuClasses.separator} />;
        if (item.kind === 'heading') return <DropdownMenu.Label key={item.id} className={menuClasses.heading}>{item.label}</DropdownMenu.Label>;
        if (item.kind === 'note') return <p key={item.id} className={menuClasses.note}>{item.label}</p>;
        if (item.kind === 'submenu') {
          return (
            <DropdownMenu.Sub key={item.id}>
              <DropdownMenu.SubTrigger className={menuClasses.row} disabled={item.disabled} data-testid={testIdOf(item)}>
                {item.icon}
                <span className="flex-1 truncate">{item.label}</span>
                {item.value ? <span className="ml-auto pl-4 text-muted-foreground">{item.value}</span> : null}
                <ChevronRight size={12} className="opacity-60" />
              </DropdownMenu.SubTrigger>
              <DropdownMenu.Portal>
                <DropdownMenu.SubContent sideOffset={4} collisionPadding={8} className={menuClasses.surface} data-testid={item.panelTestId}>
                  <MenuItems items={item.items} itemTestIdPrefix={itemTestIdPrefix} />
                </DropdownMenu.SubContent>
              </DropdownMenu.Portal>
            </DropdownMenu.Sub>
          );
        }
        return (
          <DropdownMenu.Item
            key={item.id}
            disabled={item.disabled}
            title={item.title}
            data-testid={testIdOf(item)}
            onSelect={(event) => {
              if (item.keepOpen) event.preventDefault();
              item.onSelect?.();
            }}
            className={cn(menuClasses.row, item.destructive && 'text-destructive')}
          >
            {ticks ? (
              <span className="w-3.5 shrink-0">{item.checked ? <Check size={12} className="text-workspace-accent" /> : null}</span>
            ) : null}
            {item.icon}
            <span className="flex-1 truncate">{item.label}</span>
            {item.shortcut ? <span className={menuClasses.shortcut}>{item.shortcut}</span> : null}
          </DropdownMenu.Item>
        );
      })}
    </>
  );
}

/**
 * A trigger and its menu. `trigger` replaces the default label button (e.g. a ⋯ icon button).
 * `testId` names the trigger and `${testId}-dropdown` the open panel.
 */
export function Menu({
  label,
  trigger,
  items,
  align = 'start',
  disabled,
  title,
  open,
  onOpenChange,
  testId,
  itemTestIdPrefix,
}: {
  label?: ReactNode;
  trigger?: ReactNode;
  items: MenuEntry[];
  align?: 'start' | 'end';
  disabled?: boolean;
  title?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  testId?: string;
  /** See `MenuItems`. */
  itemTestIdPrefix?: string;
}) {
  return (
    <DropdownMenu.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <DropdownMenu.Trigger asChild={!!trigger} disabled={disabled} title={title} data-testid={testId} className={trigger ? undefined : menuClasses.trigger}>
        {trigger ?? (
          <>
            {label}
            <ChevronDown size={11} className="opacity-60" />
          </>
        )}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align={align} sideOffset={5} className={menuClasses.surface} data-testid={testId ? `${testId}-dropdown` : undefined}>
          <MenuItems items={items} itemTestIdPrefix={itemTestIdPrefix} />
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/**
 * An app's menu bar in the top nav: its name, then File / Edit / View…, then anything trailing.
 * Other `nav` attributes (e.g. a `data-*` state for tests) pass through.
 */
export function MenuBar({
  title,
  leading,
  trailing,
  children,
  label,
  testId,
  className,
  ...rest
}: Omit<ComponentPropsWithoutRef<'nav'>, 'title' | 'children'> & {
  title?: ReactNode;
  leading?: ReactNode;
  trailing?: ReactNode;
  children: ReactNode;
  /** Accessible name, e.g. "Tasks menus". */
  label: string;
  testId?: string;
}) {
  return (
    <nav {...rest} className={cn('flex min-w-0 shrink-0 items-center gap-1', className)} aria-label={label} data-testid={testId}>
      {leading}
      {title ? <span className="mr-1 hidden text-xs font-semibold text-foreground sm:inline">{title}</span> : null}
      {children}
      {trailing}
    </nav>
  );
}
