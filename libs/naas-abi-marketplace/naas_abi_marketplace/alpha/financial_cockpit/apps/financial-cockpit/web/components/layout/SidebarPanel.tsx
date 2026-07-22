'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Link as AriaLink } from 'react-aria-components';

import type { CompanyConfig, PageId, SiteConfig } from '@/lib/types';
import type { EntityGalleryEntry } from '@/components/gallery/EntityGallery';
import type { NavEntry } from '@/lib/navModel';
import { formatEntityName } from '@/lib/format';
import { PerimeterSwitcher } from '@/components/layout/PerimeterSwitcher';
import { ADMIN_NAV } from '@/components/layout/AdminNavSection';

type SidebarPanelProps = {
  /** Drives the width transition; when false the panel collapses to zero width. */
  open: boolean;
  /** Section / administration entry whose subpages fill the panel. */
  activeEntry: NavEntry | null;
  pageLabels: Record<string, string>;
  currentPageId: PageId | null;
  hrefFor: (pageId: PageId) => string;
  perimeterEntries: EntityGalleryEntry[];
  switcherEntityId: string | null;
  company: CompanyConfig | null;
  site: SiteConfig | null;
  dataVersion: string | null;
  onCollapse: () => void;
};

function adminSectionFor(pathname: string): string | null {
  if (pathname === '/admin/theme' || pathname.startsWith('/admin/theme/')) return 'theme';
  if (pathname.startsWith('/admin/users')) return 'users';
  if (pathname.startsWith('/admin/analytics')) return 'analytics';
  if (pathname === '/admin' || pathname.startsWith('/admin/')) return 'perimeters';
  return null;
}

/**
 * Secondary panel — the second column of the double sidebar. Its header carries
 * the perimeter switcher (constant context), and its body lists the subpages of
 * the active group, or the Administration links. Collapsing it leaves the icon
 * rail as the sole navigation column.
 */
export function SidebarPanel({
  open,
  activeEntry,
  pageLabels,
  currentPageId,
  hrefFor,
  perimeterEntries,
  switcherEntityId,
  company,
  site,
  dataVersion,
  onCollapse,
}: SidebarPanelProps) {
  const pathname = usePathname();
  const isAdmin = activeEntry?.kind === 'administration';
  const activeAdmin = adminSectionFor(pathname);

  const title = isAdmin
    ? 'Administration'
    : activeEntry?.kind === 'section'
      ? activeEntry.label
      : '';

  return (
    <aside
      className={`shell-chrome flex h-full shrink-0 flex-col overflow-hidden border-r border-[var(--border)] transition-[width] duration-300 ease-in-out ${
        open ? 'w-64' : 'w-0'
      }`}
    >
      <div className="flex h-full min-h-0 w-64 flex-col overflow-hidden">
        <div className="flex h-[var(--topbar-height)] shrink-0 items-center gap-1 border-b border-[var(--border)] px-3">
          <PerimeterSwitcher
            entries={perimeterEntries}
            currentEntityId={switcherEntityId}
          />
          <button
            type="button"
            onClick={onCollapse}
            aria-label="Réduire le menu"
            className="shrink-0 px-2 py-1 text-base leading-none text-[var(--text-muted)] outline-none transition-colors hover:bg-[var(--accent)] hover:text-[var(--text)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary"
          >
            «
          </button>
        </div>

        {company ? (
          <div className="shrink-0 px-4 pb-2 pt-3">
            <p className="sidebar-section-label !px-0">Société</p>
            <p className="truncate text-sm font-medium text-[var(--text)]">
              {formatEntityName(company.display_name)}
            </p>
          </div>
        ) : null}
        {site ? (
          <div className="shrink-0 px-4 pb-2 pt-3">
            <p className="sidebar-section-label !px-0">Site</p>
            <p className="truncate text-sm font-medium text-[var(--text)]">
              {formatEntityName(site.name)}
            </p>
          </div>
        ) : null}

        <nav aria-label={title || 'Navigation'} className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          {title ? <p className="sidebar-section-label">{title}</p> : null}

          <div className="sidebar-nav">
            {isAdmin
              ? ADMIN_NAV.map((item) => (
                  <Link
                    key={item.id}
                    href={item.href}
                    aria-current={item.id === activeAdmin ? 'page' : undefined}
                    className={`sidebar-nav-item${item.id === activeAdmin ? ' active' : ''}`}
                  >
                    <item.icon className="sidebar-nav-icon" />
                    <span className="sidebar-nav-label">{item.label}</span>
                  </Link>
                ))
              : activeEntry?.kind === 'section'
                ? activeEntry.childIds.map((pageId) => {
                    const href = hrefFor(pageId);
                    const active =
                      currentPageId === pageId || pathname === href.split('?')[0];
                    return (
                      <AriaLink
                        key={pageId}
                        href={href}
                        className={`sidebar-nav-item${active ? ' active' : ''}`}
                      >
                        <span className="sidebar-nav-label">
                          {pageLabels[pageId] ?? pageId}
                        </span>
                      </AriaLink>
                    );
                  })
                : null}
          </div>
        </nav>

        {dataVersion ? (
          <div className="shrink-0 border-t border-[var(--border)] px-4 py-3">
            <p className="text-[0.7rem] leading-snug text-[var(--text-muted)]">
              Données actualisées le {dataVersion}
            </p>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
