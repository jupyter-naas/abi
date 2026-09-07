'use client';

import type { CompanyConfig, EntityConfig, NavSection, PageBannerConfig, PageId, SiteConfig, UserConfig } from '@/lib/types';
import type { ScenarioOption } from '@/lib/data/scenarios';
import type { EntityGalleryEntry } from '@/components/gallery/EntityGallery';
import { isConsolidation } from '@/lib/config/entityHelpers';
import { PageViewBeacon } from '@/components/analytics/PageViewBeacon';
import { CompanyPicker } from '@/components/layout/CompanyPicker';
import { ScenarioPicker } from '@/components/layout/ScenarioPicker';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { TopBarTitle } from '@/components/layout/TopBarTitle';
import { TopBarThemeSwitch } from '@/components/layout/TopBarThemeSwitch';
import { PageBanner } from '@/components/ui/PageBanner';
import { analyticsPageKey, entityPageHref } from '@/lib/routes';

type AppShellProps = {
  user: UserConfig;
  entity: EntityConfig;
  pageId: PageId;
  site: SiteConfig | null;
  company: CompanyConfig | null;
  perimeterEntries: EntityGalleryEntry[];
  isAdmin: boolean;
  allowedPages: PageId[];
  pageLabels: Record<string, string>;
  navSections: NavSection[];
  dataVersion: string | null;
  scenarios: ScenarioOption[];
  scenarioId: string | null;
  consolidationCompanies?: CompanyConfig[];
  banner?: PageBannerConfig | null;
  children: React.ReactNode;
};

export function AppShell(props: AppShellProps) {
  const {
    children,
    user,
    entity,
    pageId,
    company,
    site,
    perimeterEntries,
    isAdmin,
    allowedPages,
    pageLabels,
    navSections,
    dataVersion,
    scenarios,
    scenarioId,
    consolidationCompanies: consolidationCompaniesProp,
    banner,
  } = props;

  const consolidationCompanies =
    consolidationCompaniesProp ??
    (isConsolidation(entity) ? (entity.companies ?? []) : []);

  const analyticsPage = analyticsPageKey(
    entityPageHref(
      entity.url_slug,
      pageId,
      company?.organization_slug ?? null,
      site?.site_id ?? null,
      scenarioId,
    ),
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <PageViewBeacon page={analyticsPage} perimeter={entity.url_slug} />
      <AppSidebar
        user={user}
        perimeterEntries={perimeterEntries}
        isAdmin={isAdmin}
        entity={entity}
        pageId={pageId}
        company={company}
        site={site}
        allowedPages={allowedPages}
        pageLabels={pageLabels}
        navSections={navSections}
        scenarioId={scenarioId}
        dataVersion={dataVersion}
      />

      <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="topbar-chrome shrink-0 grid h-[var(--topbar-height)] grid-cols-[1fr_minmax(0,32rem)_1fr] items-center gap-3 border-b border-[var(--border)] px-4 md:gap-4 md:px-6">
          <div />
          <TopBarTitle>{pageLabels[pageId] ?? pageId}</TopBarTitle>
          <div className="flex justify-end">
            <TopBarThemeSwitch />
          </div>
        </header>

        {banner ? <PageBanner banner={banner} className="shrink-0" /> : null}

        {isConsolidation(entity) || scenarios.length > 0 ? (
          <div className="shrink-0 flex flex-col items-center gap-3 bg-[var(--bg)] px-4 pb-[1.5rem] pt-[1.5rem] sm:px-6 md:px-8">
            {isConsolidation(entity) ? (
              <CompanyPicker
                companies={consolidationCompanies}
                currentSlug={company?.organization_slug ?? null}
                entitySlug={entity.url_slug}
                currentPageId={pageId}
                scenarioId={scenarioId}
                variant="page"
                className="w-full max-w-xs"
              />
            ) : null}
            {scenarios.length > 0 ? (
              <ScenarioPicker
                scenarios={scenarios}
                currentScenarioId={scenarioId}
                entitySlug={entity.url_slug}
                currentPageId={pageId}
                companySlug={company?.organization_slug ?? null}
                siteSlug={site?.site_id ?? null}
                className="w-full max-w-xs"
              />
            ) : null}
          </div>
        ) : null}

        <main className="flex-1 min-h-0 overflow-y-auto bg-[var(--bg)] px-4 py-6 sm:px-6 md:px-8 md:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
