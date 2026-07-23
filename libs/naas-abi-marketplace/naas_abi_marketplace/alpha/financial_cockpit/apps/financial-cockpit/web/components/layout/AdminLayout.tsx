import type { ReactNode } from 'react';

import { AppSidebar } from '@/components/layout/AppSidebar';
import { type AdminSection } from '@/components/layout/AdminNavSection';
import { TopBarTitle } from '@/components/layout/TopBarTitle';
import { TopBarThemeSwitch } from '@/components/layout/TopBarThemeSwitch';
import { PageViewBeacon } from '@/components/analytics/PageViewBeacon';
import { getUserFromSession, requireAdmin } from '@/lib/auth/session';
import {
  getAllowedEntities,
  getAllowedPages,
  getNavSections,
  getPageLabel,
  resolveEntityEntryPath,
} from '@/lib/config/loadConfig';

type AdminLayoutProps = {
  displayName: string;
  active: AdminSection;
  children: ReactNode;
};

const TITLES: Record<AdminSection, string> = {
  perimeters: 'Périmètres',
  users: 'Utilisateurs',
  analytics: 'Analytiques',
  theme: 'Thèmes',
};

const ADMIN_ANALYTICS_PAGES: Record<AdminSection, string> = {
  perimeters: 'admin',
  users: 'admin/users',
  analytics: 'admin/analytics',
  theme: 'admin/theme',
};

export async function AdminLayout({ active, children }: AdminLayoutProps) {
  // The calling page already gated on requireAdmin; re-resolving here builds the
  // sidebar data (user + accessible perimeters) from the same session.
  const session = await requireAdmin();
  const user = await getUserFromSession(session);
  const allowed = await getAllowedEntities(session);
  const perimeterEntries = allowed
    .map((entity) => {
      const href = resolveEntityEntryPath(session, entity);
      return href ? { entity, href } : null;
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);

  const allowedPages = getAllowedPages(session);
  const pageLabels = Object.fromEntries(
    allowedPages.map((pageId) => [pageId, getPageLabel(pageId)]),
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <PageViewBeacon page={ADMIN_ANALYTICS_PAGES[active]} perimeter={null} />
      <AppSidebar
        user={user}
        perimeterEntries={perimeterEntries}
        isAdmin
        allowedPages={allowedPages}
        pageLabels={pageLabels}
        navSections={getNavSections()}
      />
      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="topbar-chrome shrink-0 grid grid-cols-[1fr_minmax(0,32rem)_1fr] items-center gap-3 border-b border-[var(--border)] px-4 py-4 md:gap-4 md:px-6 md:py-4">
          <div />
          <TopBarTitle>{TITLES[active]}</TopBarTitle>
          <div className="flex justify-end">
            <TopBarThemeSwitch />
          </div>
        </header>
        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto bg-[var(--bg)] px-4 py-6 sm:px-6 md:px-8 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
