/**
 * Platform Settings › Theme: the living reference of the design kit (`components/ui`).
 * Every kit module is listed here, with what it is for, and shown on the page in its
 * states, with the platform's own tokens and branding. No React: the nav and the
 * middleware read the path, and a test checks that no kit module is left off the page.
 */

export const PLATFORM_THEME_PATH = '/settings/theme';

export type KitEntry = {
  /** The module under `components/ui`, without extension. */
  module: string;
  /** The section's anchor on the page. */
  id: string;
  label: string;
  /** What it is for, and what it replaces. */
  use: string;
};

export const KIT_CATALOG: readonly KitEntry[] = [
  { module: 'button', id: 'buttons', label: 'Buttons', use: 'Every action. Primary once per view; secondary, ghost, destructive; icon buttons in toolbars. 36px in headers (md), 32px inline (sm).' },
  { module: 'badge', id: 'badges', label: 'Badges', use: 'A status, a kind, a count beside a label. Mono for identifiers.' },
  { module: 'input', id: 'fields', label: 'Inputs', use: 'Input, Select, Textarea. Always inside a Field.' },
  { module: 'checkbox', id: 'fields', label: 'Checkbox', use: 'A yes/no choice in a form or a table row.' },
  { module: 'field', id: 'fields', label: 'Field', use: 'Label, control, hint or error. Replaces SettingsField, .org-settings-field, .account-profile-field.' },
  { module: 'search-box', id: 'search', label: 'Search box', use: 'The one search field: neutral border on focus, clear button, Escape clears.' },
  { module: 'notice', id: 'notices', label: 'Notice', use: 'Inline success, error, warning or info line. Replaces SettingsNotice and the Data explorer notice.' },
  { module: 'empty-state', id: 'empty', label: 'Empty state', use: 'A list, table or pane with nothing in it. Framed on a page, plain in a pane.' },
  { module: 'spinner', id: 'loading', label: 'Loading', use: 'Spinner inside buttons and rows; Loading for a pane or a page.' },
  { module: 'card', id: 'cards', label: 'Card', use: 'A titled block of a page. Replaces SettingsSection and the System section.' },
  { module: 'page-header', id: 'page-header', label: 'Page header', use: 'Title, count, description, actions top-right.' },
  { module: 'kpi-card', id: 'cards', label: 'KPI card', use: 'One number with its label and trend.' },
  { module: 'toolbar', id: 'toolbar', label: 'Toolbar', use: 'The bar above a pane: search and filters left, actions right.' },
  { module: 'tabs', id: 'tabs', label: 'Tabs', use: 'Underline on a pane edge, segmented inside a toolbar. Arrow keys move.' },
  { module: 'menu', id: 'menus', label: 'Menus', use: 'Menu bars (File / Edit / View), overflow (⋯) and row menus, one style, on Radix. Every app bar (Apps, Chat, Datasets, Documents, Events, Files, Graph, Home, Maps, Ontology, Search, Sheets, Slides, Tasks) is a MenuBar of Menus from data; testId + itemTestIdPrefix name the trigger, panel and rows.' },
  { module: 'tree-row', id: 'tree', label: 'List and tree rows', use: 'Sidebar lists and trees: twisty, icon, label, hover actions.' },
  { module: 'split-pane', id: 'split', label: 'Split pane', use: 'The drag handle between two columns (sidebar, settings nav, AI pane).' },
  { module: 'dialog', id: 'dialogs', label: 'Dialog', use: 'Every modal, five widths: sm, md, lg, xl, full. Focus trapped, Escape closes, ⌘↵ submits.' },
  { module: 'dialogs', id: 'dialogs', label: 'Confirm and prompt', use: 'useConfirm (with type-to-confirm) and usePrompt instead of window.confirm / prompt.' },
  { module: 'toast', id: 'toasts', label: 'Toast', use: 'toast.success / toast.error from anywhere; one stack for the whole app.' },
];

/** The page's sections, in order, each once. */
export function themeSections(catalog: readonly KitEntry[] = KIT_CATALOG): { id: string; entries: KitEntry[] }[] {
  const sections: { id: string; entries: KitEntry[] }[] = [];
  for (const entry of catalog) {
    const section = sections.find((s) => s.id === entry.id);
    if (section) section.entries.push(entry);
    else sections.push({ id: entry.id, entries: [entry] });
  }
  return sections;
}
