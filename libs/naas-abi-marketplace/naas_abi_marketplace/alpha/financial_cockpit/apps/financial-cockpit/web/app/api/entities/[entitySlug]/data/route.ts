import { NextResponse } from 'next/server';
import { notFound } from 'next/navigation';

import {
  canAccess,
  getEntity,
  isPageEnabled,
} from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';
import { normalizePageId } from '@/lib/types';
import { preparePageDatasets } from '@/lib/data/preparePageDatasets';
import { loadPageDatasets } from '@/lib/data/datasets';
import { loadFilterScenarios, scenariosForEntity } from '@/lib/data/globalFilters';
import { resolveActiveScenario } from '@/lib/data/scenarios';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ entitySlug: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { entitySlug } = await context.params;
  const entity = await getEntity(entitySlug);
  if (!entity) {
    notFound();
  }

  const url = new URL(request.url);
  const pageParam = normalizePageId(url.searchParams.get('page') ?? '');
  if (!pageParam) {
    return NextResponse.json({ error: 'Invalid page' }, { status: 400 });
  }

  if (!isPageEnabled(pageParam)) {
    notFound();
  }

  if (!canAccess(session, entity.entity_id, pageParam)) {
    notFound();
  }

  const companySlug = url.searchParams.get('company');
  const organizationSlug = companySlug || null;
  const scenarioId = url.searchParams.get('scenario');

  const rawDatasets = await loadPageDatasets(entity.entity_id, pageParam);
  const filterScenarios = await loadFilterScenarios();
  const scenarioOptions = scenariosForEntity(
    filterScenarios,
    entity.entity_id,
    organizationSlug,
  );
  const activeScenario = resolveActiveScenario(scenarioId, scenarioOptions);
  const datasets = preparePageDatasets(entity, rawDatasets, {
    organizationSlug,
    scenarioId: activeScenario?.id ?? null,
    scenarioSplit: activeScenario?.split ?? null,
  });

  return NextResponse.json({
    entity_id: entity.entity_id,
    page: pageParam,
    datasets,
    filters: {
      scenarios: scenarioOptions,
    },
  });
}
