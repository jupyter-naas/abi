import 'server-only';

import { notFound, redirect } from 'next/navigation';

import type { PageId, SectionProps } from '@/lib/types';
import { normalizePageId } from '@/lib/types';
import {
  getAllowedEntities,
  getAllowedPages,
  getCompany,
  getConsolidationCompanies,
  getEntity,
  getPageBanner,
  getPageLabel,
  getNavSections,
  getSite,
  isConsolidation,
  isPageEnabled,
  resolveEntityEntryPath,
} from '@/lib/config/loadConfig';
import {
  getUserFromSession,
  isAdminSession,
  requireEntityPageAccess,
} from '@/lib/auth/session';
import { preparePageDatasets } from '@/lib/data/preparePageDatasets';
import { applyRecordFiltersToDatasets } from '@/lib/data/filter';
import {
  extractScenariosFromDatasets,
  extractTreasuryScenarios,
  mergeScenarioOptions,
  resolveActiveScenario,
  resolveCurrentYearScenario,
  scenarioIdForNavigation,
} from '@/lib/data/scenarios';
import {
  companiesForEntity,
  loadFilterEntities,
  loadFilterScenarios,
  scenariosForEntity,
} from '@/lib/data/globalFilters';
import { loadPageDatasets, getEntityDataVersion } from '@/lib/data/datasets';
import { entityPageHref, THEME_PAGE_PATH } from '@/lib/routes';
import { AppShell } from '@/components/layout/AppShell';
import { SECTION_COMPONENTS, isRegisteredPage } from '@/components/dashboard/sections/registry';

type EntityPageParams = {
  entitySlug: string;
  pageId?: string;
  siteSlug?: string;
};

type EntityPageProps = {
  params: Promise<EntityPageParams>;
  searchParams?: Promise<{ scenario?: string; company?: string }>;
};

export function createEntityPage(fixedPageId?: PageId) {
  return async function EntityPage({ params, searchParams }: EntityPageProps) {
    const resolved = await params;
    const resolvedSearch = searchParams ? await searchParams : {};
    const rawPageId = fixedPageId ?? resolved.pageId ?? '';
    const pageId = normalizePageId(rawPageId);

    if (!pageId) {
      notFound();
    }

    if (pageId === 'theme') {
      redirect(THEME_PAGE_PATH);
    }

    const entity = await getEntity(resolved.entitySlug);
    if (!entity) {
      notFound();
    }

    // Canonicalize legacy page ids in the URL (e.g. /invoices → /customer-invoices).
    if (!fixedPageId && resolved.pageId && resolved.pageId !== pageId) {
      redirect(
        entityPageHref(
          entity.url_slug,
          pageId,
          resolvedSearch.company ?? null,
          resolved.siteSlug ?? null,
          resolvedSearch.scenario ?? null,
        ),
      );
    }

    if (!isPageEnabled(pageId)) {
      notFound();
    }

    const session = await requireEntityPageAccess(entity.entity_id, pageId).catch(
      () => notFound(),
    );
    const user = await getUserFromSession(session);

    const siteSlug = resolved.siteSlug;
    const site = siteSlug ? getSite(entity, siteSlug) ?? null : null;
    if (siteSlug && !site) {
      notFound();
    }

    const companySlug = resolvedSearch.company?.trim() || null;
    const company = companySlug ? getCompany(entity, companySlug) ?? null : null;
    if (companySlug) {
      if (!isConsolidation(entity)) {
        notFound();
      }
      if (!company) {
        notFound();
      }
    }

    const rawDatasets = await loadPageDatasets(entity.entity_id, pageId);
    const organizationSlug = company?.organization_slug ?? null;
    const siteId = site?.site_id ?? null;
    const preScenarioDatasets = applyRecordFiltersToDatasets(rawDatasets, {
      siteId,
      organizationSlug,
    });
    const filterEntities = await loadFilterEntities();
    const filterScenarios = await loadFilterScenarios();
    const globalScenarioOptions = scenariosForEntity(
      filterScenarios,
      entity.entity_id,
      organizationSlug,
    );
    // Treasury derives its scenarios from the bank fiscal periods (on the
    // cash_position dataset) and does not merge the invoice-derived scenarios.
    const scenarios =
      pageId === 'treasury'
        ? extractTreasuryScenarios(preScenarioDatasets)
        : mergeScenarioOptions(
            globalScenarioOptions,
            extractScenariosFromDatasets(preScenarioDatasets),
          );
    const requestedScenario = resolvedSearch.scenario;
    if (requestedScenario === undefined) {
      const defaultScenario = resolveCurrentYearScenario(scenarios);
      if (defaultScenario) {
        redirect(
          entityPageHref(
            entity.url_slug,
            pageId,
            company?.organization_slug ?? null,
            site?.site_id ?? null,
            defaultScenario.id,
          ),
        );
      }
    }
    const activeScenario = resolveActiveScenario(requestedScenario, scenarios);
    const scenarioId = scenarioIdForNavigation(requestedScenario, activeScenario);
    const scenarioSplit = activeScenario?.split ?? null;
    const consolidationCompanies = isConsolidation(entity)
      ? companiesForEntity(filterEntities, entity.entity_id) ??
        getConsolidationCompanies(entity)
      : [];
    const datasets = preparePageDatasets(entity, rawDatasets, {
      siteId,
      organizationSlug,
      scenarioId: activeScenario?.id ?? null,
      scenarioSplit,
    });
    const dataVersion = await getEntityDataVersion(entity.entity_id);

    if (!isRegisteredPage(pageId)) {
      notFound();
    }

    const Section = SECTION_COMPONENTS[pageId];

    const sectionProps: SectionProps = {
      user,
      entity,
      site,
      company,
      datasets,
    };

    const allowedEntities = await getAllowedEntities(session);
    const isAdmin = await isAdminSession(session);
    const perimeterEntries = allowedEntities
      .map((allowedEntity) => {
        const href = resolveEntityEntryPath(session, allowedEntity);
        return href ? { entity: allowedEntity, href } : null;
      })
      .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
    const allowedPages = getAllowedPages(session, entity.entity_id);
    const pageLabels = Object.fromEntries(
      allowedPages.map((id) => [id, getPageLabel(id)]),
    );
    const navSections = getNavSections();
    const banner = getPageBanner(pageId);

    return (
      <AppShell
        user={user}
        entity={entity}
        pageId={pageId}
        site={site}
        company={company}
        perimeterEntries={perimeterEntries}
        isAdmin={isAdmin}
        allowedPages={allowedPages}
        pageLabels={pageLabels}
        navSections={navSections}
        dataVersion={dataVersion}
        scenarios={scenarios}
        scenarioId={scenarioId}
        consolidationCompanies={consolidationCompanies}
        banner={banner}
      >
        <Section {...sectionProps} />
      </AppShell>
    );
  };
}
