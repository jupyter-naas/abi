/**
 * Shell CSS class tokens (phase 1: disambiguation naming, not full ontology/TTL).
 *
 * Naming: {surface}-{region}-{element}[-{modifier}] in kebab-case.
 * Styles are defined in globals.css; exports are class name strings for JSX.
 */
export const shellTokens = {
  sidebar: {
    /** Primary label typography for interactive rows in the desktop sidebar nav lists. */
    listRow: 'shell-sidebar-list-row',
    /** Collapsible subsection headers inside the sidebar (e.g. "Starred", "Apps"). */
    sectionLabel: 'shell-sidebar-section-label',
  },
  mobile: {
    moreSheet: {
      /** Grid item labels in the mobile shell "More" bottom sheet. */
      gridLabel: 'shell-mobile-more-sheet-grid-label',
    },
  },
} as const;
