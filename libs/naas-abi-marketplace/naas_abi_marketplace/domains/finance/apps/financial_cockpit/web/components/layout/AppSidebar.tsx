'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import type {
  CompanyConfig,
  EntityConfig,
  NavSection,
  PageId,
  SiteConfig,
  UserConfig,
} from '@/lib/types';
import type { EntityGalleryEntry } from '@/components/gallery/EntityGallery';
import {
  ADMIN_SECTION_ID,
  buildNavEntries,
  entryKey,
  sectionIdForPage,
} from '@/lib/navModel';
import { entityPageHref, isSidebarFooterPage } from '@/lib/routes';
import { readLastPerimeterId, writeLastPerimeterId } from '@/lib/lastPerimeter';
import { SidebarRail } from '@/components/layout/SidebarRail';
import { SidebarPanel } from '@/components/layout/SidebarPanel';

/** Persists the user's panel-collapse choice across per-route AppShell remounts. */
const PANEL_COLLAPSED_KEY = 'fin-sidebar-collapsed';

type AppSidebarProps = {
  user: UserConfig;
  perimeterEntries: EntityGalleryEntry[];
  isAdmin: boolean;
  /** Active perimeter, or null on admin / settings screens. */
  entity?: EntityConfig | null;
  pageId?: PageId | null;
  company?: CompanyConfig | null;
  site?: SiteConfig | null;
  allowedPages?: PageId[];
  pageLabels?: Record<string, string>;
  navSections?: NavSection[];
  scenarioId?: string | null;
  dataVersion?: string | null;
};

/**
 * Double sidebar shared by entity, admin and settings screens. The icon
 * {@link SidebarRail} lists top-level groups; selecting one reveals its
 * subpages in the {@link SidebarPanel}. The panel follows the current route on
 * navigation, but can also be opened ahead of navigating or collapsed away to
 * leave the rail as the only navigation column.
 */
export function AppSidebar({
  user,
  perimeterEntries,
  isAdmin,
  entity = null,
  pageId = null,
  company = null,
  site = null,
  allowedPages = [],
  pageLabels = {},
  navSections = [],
  scenarioId = null,
  dataVersion = null,
}: AppSidebarProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [lastPerimeterId, setLastPerimeterId] = useState<string | null>(() =>
    readLastPerimeterId(),
  );

  useEffect(() => {
    if (entity?.entity_id) {
      writeLastPerimeterId(entity.entity_id);
      setLastPerimeterId(entity.entity_id);
      return;
    }
    setLastPerimeterId(readLastPerimeterId());
  }, [entity?.entity_id]);

  const switcherEntityId = entity?.entity_id ?? lastPerimeterId;

  const navEntity = useMemo(() => {
    if (entity) return entity;
    if (!switcherEntityId) return null;
    return (
      perimeterEntries.find((entry) => entry.entity.entity_id === switcherEntityId)
        ?.entity ?? null
    );
  }, [entity, perimeterEntries, switcherEntityId]);

  const adminActive = pathname === '/admin' || pathname.startsWith('/admin/');

  const entries = useMemo(
    () =>
      buildNavEntries(
        allowedPages.filter((id) => !isSidebarFooterPage(id)),
        navSections,
        isAdmin,
      ),
    [allowedPages, navSections, isAdmin],
  );

  // Panel entry the current route belongs to: the admin group on /admin
  // screens, the owning group of the active page, or null for a flat page.
  const routeKey = adminActive
    ? ADMIN_SECTION_ID
    : sectionIdForPage(pageId, navSections);

  const [activeKey, setActiveKey] = useState<string | null>(routeKey);
  // AppShell remounts on every navigation, so the collapse preference is kept
  // in sessionStorage to survive route changes (mirrors the old sidebar).
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(sessionStorage.getItem(PANEL_COLLAPSED_KEY) === '1');
    } catch {
      /* private mode — fall back to expanded */
    }
  }, []);

  function updateCollapsed(next: boolean) {
    setCollapsed(next);
    try {
      sessionStorage.setItem(PANEL_COLLAPSED_KEY, next ? '1' : '0');
    } catch {
      /* ignore persistence failures */
    }
  }

  // Follow the route: after any navigation the panel reflects where the user
  // landed. Manual section selection (below) is untouched — it changes no URL.
  useEffect(() => {
    setActiveKey(routeKey);
  }, [routeKey]);

  const activeEntry = useMemo(
    () => entries.find((entry) => entryKey(entry) === activeKey) ?? null,
    [entries, activeKey],
  );

  const panelOpen = !collapsed && activeEntry !== null;

  function handleSelectSection(key: string) {
    const entry = entries.find((candidate) => entryKey(candidate) === key);
    if (!entry) return;

    // Re-clicking the group that owns the current route collapses the panel.
    if (key === routeKey && panelOpen) {
      updateCollapsed(true);
      return;
    }

    setActiveKey(key);
    updateCollapsed(false);

    // Selecting a group navigates into it so the panel and content stay in
    // sync; multi-page groups land on their first page.
    if (entry.kind === 'section') {
      router.push(hrefFor(entry.childIds[0]));
    } else if (entry.kind === 'administration') {
      router.push('/admin');
    }
  }

  const hrefFor = (targetPageId: PageId) =>
    entityPageHref(
      navEntity?.url_slug ?? '',
      targetPageId,
      company?.organization_slug,
      site?.site_id,
      scenarioId,
    );

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/login');
    router.refresh();
  }

  return (
    <>
      <SidebarRail
        entries={entries}
        pageLabels={pageLabels}
        currentPageId={pageId}
        adminActive={adminActive}
        activeKey={panelOpen ? activeKey : null}
        hrefFor={hrefFor}
        onSelectSection={handleSelectSection}
        user={user}
        onLogout={handleLogout}
      />
      <SidebarPanel
        open={panelOpen}
        activeEntry={activeEntry}
        pageLabels={pageLabels}
        currentPageId={pageId}
        hrefFor={hrefFor}
        perimeterEntries={perimeterEntries}
        switcherEntityId={switcherEntityId}
        company={company}
        site={site}
        dataVersion={dataVersion}
        onCollapse={() => updateCollapsed(true)}
      />
    </>
  );
}
