import type { SidebarSection } from '@/stores/workspace';

/**
 * Shared between SectionPanel (which renders each section's content) and
 * TopNav (which now paints the active section's title, since the panel no
 * longer carries its own title row).
 */
export const SECTION_LABELS: Record<SidebarSection, string> = {
  home: 'Home',
  workspaces: 'Workspaces',
  maps: 'Maps',
  search: 'Search',
  chat: 'Chat',
  ontology: 'Ontology',
  graph: 'Knowledge Graph',
  files: 'Files',
  datasets: 'Datasets',
  code: 'Code',
  slides: 'Slides',
  apps: 'Apps',
  marketplace: 'Marketplace',
  settings: 'Settings',
  events: 'Events',
  infrastructure: 'Infrastructure',
};

/** Panel titles that open the section home. Slides goes to the cover gallery. */
export const SECTION_HOME_HREF: Partial<Record<SidebarSection, string>> = {
  slides: '/slides',
};
