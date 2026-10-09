/**
 * Shared classes for the TopNav app menu bars built on Radix DropdownMenu
 * (Files, Search, Ontology, Knowledge Graph). The highlight matches the
 * hand-rolled bars (Apps, Slides, Documents, Sheets): grey `bg-muted` under the
 * cursor or keyboard focus, and on a trigger while its menu is open.
 */

/** A menu item, radio item, checkbox item or sub-trigger. */
export const APP_MENU_ROW =
  'flex cursor-default select-none items-center gap-2 px-3 py-1.5 text-xs outline-none transition-colors ![border-radius:0] data-[highlighted]:bg-muted data-[state=open]:bg-muted data-[disabled]:opacity-50';

/** The dropdown / sub-menu panel. */
export const APP_MENU_SURFACE =
  'z-[300] min-w-[190px] border-0 bg-card p-1 text-foreground !shadow-none outline-none !ring-0 focus:!ring-0 focus-visible:!ring-0 ![border-radius:0]';

/** The File / Edit / View button on the bar. */
export const APP_MENU_TRIGGER =
  'flex items-center gap-1 rounded border-0 bg-transparent px-2 py-1 text-xs font-medium text-foreground/90 shadow-none outline-none ring-0 transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0 data-[state=open]:bg-muted data-[state=open]:text-foreground data-[state=open]:shadow-none';
