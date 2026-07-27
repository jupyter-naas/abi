import type { Dataset } from '@/lib/types';

export type ScenarioSplit = 'date_month' | 'date_year';

export type ScenarioOption = {
  id: string;
  label: string;
  split: ScenarioSplit;
};

export const SCENARIO_GROUP_LABELS: Record<ScenarioSplit, string> = {
  date_month: 'Par mois',
  date_year: 'Par année',
};

export function groupScenarios(
  scenarios: ScenarioOption[],
): Record<ScenarioSplit, ScenarioOption[]> {
  const grouped: Record<ScenarioSplit, ScenarioOption[]> = {
    date_month: [],
    date_year: [],
  };
  for (const scenario of scenarios) {
    grouped[scenario.split].push(scenario);
  }
  grouped.date_month.sort((a, b) => b.id.localeCompare(a.id));
  grouped.date_year.sort((a, b) => b.id.localeCompare(a.id));
  return grouped;
}

export type ScenarioYearGroup = {
  yearId: string;
  year: ScenarioOption;
  months: ScenarioOption[];
};

/** Nest month scenarios under their preprocessed year option. */
export function groupScenariosByYear(scenarios: ScenarioOption[]): ScenarioYearGroup[] {
  const yearById = new Map<string, ScenarioOption>();
  const monthsByYear = new Map<string, ScenarioOption[]>();

  for (const scenario of scenarios) {
    if (scenario.split === 'date_year') {
      yearById.set(scenario.id, scenario);
      continue;
    }
    if (scenario.split === 'date_month' && scenario.id.length >= 7) {
      const yearId = scenario.id.slice(0, 4);
      const bucket = monthsByYear.get(yearId) ?? [];
      bucket.push(scenario);
      monthsByYear.set(yearId, bucket);
    }
  }

  const yearIds = new Set([...yearById.keys(), ...monthsByYear.keys()]);
  return [...yearIds]
    .sort((a, b) => b.localeCompare(a))
    .map((yearId) => ({
      yearId,
      year: yearById.get(yearId) ?? {
        id: yearId,
        label: yearId,
        split: 'date_year',
      },
      months: (monthsByYear.get(yearId) ?? []).sort((a, b) => b.id.localeCompare(a.id)),
    }));
}

export function yearIdForScenario(scenario: ScenarioOption): string | null {
  if (scenario.split === 'date_year') {
    return scenario.id;
  }
  if (scenario.split === 'date_month' && scenario.id.length >= 4) {
    return scenario.id.slice(0, 4);
  }
  return null;
}

export function mergeScenarioOptions(
  ...lists: ScenarioOption[][]
): ScenarioOption[] {
  const byKey = new Map<string, ScenarioOption>();
  for (const list of lists) {
    for (const scenario of list) {
      byKey.set(`${scenario.split}:${scenario.id}`, scenario);
    }
  }
  return [...byKey.values()].sort((a, b) => {
    if (a.split !== b.split) {
      return a.split === 'date_month' ? -1 : 1;
    }
    return b.id.localeCompare(a.id);
  });
}

export function extractScenariosFromDatasets(
  datasets: Record<string, Dataset>,
): ScenarioOption[] {
  // Any page dataset may embed its scenario metadata (unpaid_clients, pnl
  // actuals…). Treasury is the exception and keeps its own extractor below.
  const lists = Object.entries(datasets)
    .filter(([key]) => key !== 'cash_position')
    .map(([, dataset]) => {
      const metadata = (dataset as Dataset & { scenarios?: ScenarioOption[] })
        .scenarios;
      if (!Array.isArray(metadata)) {
        return [];
      }
      return metadata.filter(
        (scenario): scenario is ScenarioOption =>
          (scenario.split === 'date_month' || scenario.split === 'date_year') &&
          typeof scenario.id === 'string' &&
          typeof scenario.label === 'string',
      );
    });
  return mergeScenarioOptions(...lists);
}

/**
 * Treasury scenarios come from the bank ``period_start`` / ``period_end`` columns,
 * emitted as ``date_year`` options on the ``cash_position`` dataset. The treasury
 * page uses these exclusively (it does not merge the invoice-derived scenarios).
 */
export function extractTreasuryScenarios(
  datasets: Record<string, Dataset>,
): ScenarioOption[] {
  const position = datasets.cash_position;
  if (!position) {
    return [];
  }
  const metadata = (position as Dataset & { scenarios?: ScenarioOption[] }).scenarios;
  if (!Array.isArray(metadata)) {
    return [];
  }
  return metadata.filter(
    (scenario): scenario is ScenarioOption =>
      (scenario.split === 'date_month' || scenario.split === 'date_year') &&
      typeof scenario.id === 'string' &&
      typeof scenario.label === 'string',
  );
}

export const ALL_SCENARIOS_SCENARIO_ID = 'all';

export function resolveCurrentYearScenario(
  scenarios: ScenarioOption[],
  referenceDate: Date = new Date(),
): ScenarioOption | null {
  const yearId = String(referenceDate.getFullYear());
  const match = scenarios.find(
    (scenario) => scenario.split === 'date_year' && scenario.id === yearId,
  );
  if (match) {
    return match;
  }
  const yearScenarios = scenarios.filter((scenario) => scenario.split === 'date_year');
  return yearScenarios.sort((a, b) => b.id.localeCompare(a.id))[0] ?? null;
}

export function resolveActiveScenario(
  scenarioId: string | null | undefined,
  scenarios: ScenarioOption[],
  referenceDate: Date = new Date(),
): ScenarioOption | null {
  const trimmed = scenarioId?.trim();
  if (trimmed === ALL_SCENARIOS_SCENARIO_ID) {
    return null;
  }
  if (trimmed) {
    return scenarios.find((scenario) => scenario.id === trimmed) ?? null;
  }
  return resolveCurrentYearScenario(scenarios, referenceDate);
}

export function resolveActiveScenarioId(
  scenarioId: string | null | undefined,
  scenarios: ScenarioOption[],
  referenceDate: Date = new Date(),
): string | null {
  return resolveActiveScenario(scenarioId, scenarios, referenceDate)?.id ?? null;
}

export function scenarioIdForNavigation(
  requestedScenario: string | null | undefined,
  activeScenario: ScenarioOption | null,
): string | null {
  if (activeScenario) {
    return activeScenario.id;
  }
  if (requestedScenario?.trim() === ALL_SCENARIOS_SCENARIO_ID) {
    return ALL_SCENARIOS_SCENARIO_ID;
  }
  return null;
}

export function filterScenariosByQuery(
  scenarios: ScenarioOption[],
  query: string,
): ScenarioOption[] {
  const normalized = query.trim().toLocaleLowerCase('fr');
  if (!normalized) {
    return scenarios;
  }
  return scenarios.filter((scenario) => {
    const haystack = `${scenario.label} ${scenario.id} ${SCENARIO_GROUP_LABELS[scenario.split]}`.toLocaleLowerCase(
      'fr',
    );
    return haystack.includes(normalized);
  });
}
