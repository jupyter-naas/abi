import type { NavSection, PageId } from '@/lib/types';
import { isSidebarFooterPage } from '@/lib/routes';

/** Section id reserved for the admin group; it maps to absolute /admin routes. */
export const ADMIN_SECTION_ID = 'administration';

/**
 * A rail entry: a flat top-level page, a group that owns subpages (shown in the
 * secondary panel), or the Administration group. Shared by the icon rail and
 * the secondary panel so both agree on structure and ordering.
 */
export type NavEntry =
  | { kind: 'page'; pageId: PageId }
  | { kind: 'section'; id: string; label: string; childIds: PageId[] }
  | { kind: 'administration' };

/**
 * Build the ordered rail model from the user's allowed pages and the configured
 * nav sections. Grouped pages become `section` entries; the Administration
 * section becomes an `administration` entry (admins only); any remaining
 * ungrouped, non-footer page becomes a flat `page` entry.
 */
export function buildNavEntries(
  pages: PageId[],
  navSections: NavSection[],
  isAdmin: boolean,
): NavEntry[] {
  const pageSet = new Set(pages);
  const entries: NavEntry[] = [];
  const consumed = new Set<PageId>();

  for (const section of navSections) {
    if (section.id === ADMIN_SECTION_ID) {
      if (isAdmin) {
        entries.push({ kind: 'administration' });
      }
      continue;
    }

    const childIds = section.pageIds.filter((id) => pageSet.has(id));
    for (const id of childIds) {
      consumed.add(id);
    }
    if (childIds.length === 0) {
      continue;
    }
    entries.push({
      kind: 'section',
      id: section.id,
      label: section.label,
      childIds: [...childIds],
    });
  }

  for (const pageId of pages) {
    if (consumed.has(pageId) || isSidebarFooterPage(pageId)) {
      continue;
    }
    entries.push({ kind: 'page', pageId });
  }

  return entries;
}

/** Stable id for a rail entry — used as the active-panel key. */
export function entryKey(entry: NavEntry): string {
  if (entry.kind === 'administration') return ADMIN_SECTION_ID;
  if (entry.kind === 'section') return entry.id;
  return `page:${entry.pageId}`;
}

/** The panel-owning section id for a page, or null when the page is flat. */
export function sectionIdForPage(
  pageId: PageId | null,
  navSections: NavSection[],
): string | null {
  if (!pageId) return null;
  const section = navSections.find(
    (candidate) =>
      candidate.id !== ADMIN_SECTION_ID && candidate.pageIds.includes(pageId),
  );
  return section?.id ?? null;
}
