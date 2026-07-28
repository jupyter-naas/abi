'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Button,
  Label,
  ListBox,
  ListBoxItem,
  ListBoxSection,
  Popover,
  Select,
} from 'react-aria-components';

import {
  ALL_SCENARIOS_SCENARIO_ID,
  filterScenariosByQuery,
  groupScenariosByYear,
  SCENARIO_GROUP_LABELS,
  yearIdForScenario,
  type ScenarioOption,
} from '@/lib/data/scenarios';
import { entityPageHref } from '@/lib/routes';
import {
  fieldInput,
  listBoxItemPage,
  listBoxPage,
  popoverPage,
  selectTriggerPage,
} from '@/lib/ariaStyles';

const ALL_SCENARIOS_KEY = '__all__';
const ALL_SCENARIOS_LABEL = 'Tous les scénarios';

type ScenarioPickerProps = {
  scenarios: ScenarioOption[];
  currentScenarioId: string | null;
  entitySlug: string;
  currentPageId: string;
  companySlug?: string | null;
  siteSlug?: string | null;
  className?: string;
};

function scenarioItemId(scenario: ScenarioOption): string {
  return `${scenario.split}:${scenario.id}`;
}

function activeScenarioFromId(
  scenarios: ScenarioOption[],
  currentScenarioId: string | null,
): ScenarioOption | null {
  if (!currentScenarioId || currentScenarioId === ALL_SCENARIOS_SCENARIO_ID) {
    return null;
  }
  const matches = scenarios.filter((scenario) => scenario.id === currentScenarioId);
  return matches[0] ?? null;
}

export function ScenarioPicker({
  scenarios,
  currentScenarioId,
  entitySlug,
  currentPageId,
  companySlug,
  siteSlug,
  className = 'w-full',
}: ScenarioPickerProps) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set());

  const yearGroups = useMemo(() => groupScenariosByYear(scenarios), [scenarios]);
  const filteredScenarios = useMemo(
    () => filterScenariosByQuery(scenarios, query),
    [scenarios, query],
  );
  const isSearching = query.trim().length > 0;
  const activeScenario = activeScenarioFromId(scenarios, currentScenarioId);

  useEffect(() => {
    const yearId = activeScenario ? yearIdForScenario(activeScenario) : null;
    if (!yearId) {
      return;
    }
    setExpandedYears((current) => new Set(current).add(yearId));
  }, [activeScenario]);

  if (scenarios.length === 0) {
    return null;
  }

  const scenarioByItemId = new Map(
    scenarios.map((scenario) => [scenarioItemId(scenario), scenario]),
  );
  const selectedKey = activeScenario ? scenarioItemId(activeScenario) : ALL_SCENARIOS_KEY;
  const triggerLabel = activeScenario?.label ?? ALL_SCENARIOS_LABEL;

  function buildPath(scenario: ScenarioOption | null): string {
    return entityPageHref(
      entitySlug,
      currentPageId,
      companySlug,
      siteSlug,
      scenario?.id ?? ALL_SCENARIOS_SCENARIO_ID,
    );
  }

  function toggleYear(yearId: string) {
    setExpandedYears((current) => {
      const next = new Set(current);
      if (next.has(yearId)) {
        next.delete(yearId);
      } else {
        next.add(yearId);
      }
      return next;
    });
  }

  function renderMonthItem(scenario: ScenarioOption) {
    const itemId = scenarioItemId(scenario);
    return (
      <ListBoxItem
        key={itemId}
        id={itemId}
        textValue={scenario.label}
        className={`${listBoxItemPage} !pl-10 !text-sm !font-medium !normal-case !tracking-normal`}
      >
        {scenario.label}
      </ListBoxItem>
    );
  }

  function renderSearchItem(scenario: ScenarioOption) {
    const itemId = scenarioItemId(scenario);
    const prefix =
      scenario.split === 'date_year'
        ? SCENARIO_GROUP_LABELS.date_year
        : SCENARIO_GROUP_LABELS.date_month;
    return (
      <ListBoxItem
        key={itemId}
        id={itemId}
        textValue={`${prefix} ${scenario.label}`}
        className={listBoxItemPage}
      >
        {scenario.label}
      </ListBoxItem>
    );
  }

  function renderYearHierarchy() {
    return yearGroups.map((group) => {
      const expanded = expandedYears.has(group.yearId);
      const hasMonths = group.months.length > 0;
      const yearItemId = scenarioItemId(group.year);

      return (
        <ListBoxSection key={group.yearId}>
          <ListBoxItem
            id={yearItemId}
            textValue={group.year.label}
            className={listBoxItemPage}
          >
            <span className="flex w-full items-center gap-2">
              {hasMonths ? (
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-label={`${expanded ? 'Masquer' : 'Afficher'} les mois de ${group.year.label}`}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleYear(group.yearId);
                  }}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[var(--text-muted)] outline-none transition-colors hover:bg-white/10 hover:text-[var(--text)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary"
                >
                  <span aria-hidden>{expanded ? '▾' : '▸'}</span>
                </button>
              ) : (
                <span className="w-8 shrink-0" aria-hidden />
              )}
              <span className="flex-1 truncate text-center">{group.year.label}</span>
            </span>
          </ListBoxItem>
          {expanded && hasMonths
            ? group.months.map((month) => renderMonthItem(month))
            : null}
        </ListBoxSection>
      );
    });
  }

  return (
    <Select
      aria-label="Scénario"
      selectedKey={selectedKey}
      onSelectionChange={(key) => {
        if (key === ALL_SCENARIOS_KEY) {
          router.push(buildPath(null));
          return;
        }
        const scenario = scenarioByItemId.get(String(key));
        if (scenario) {
          router.push(buildPath(scenario));
        }
      }}
      className={className}
    >
      <Label className="sr-only">Scénario</Label>
      <Button className={selectTriggerPage}>
        <span className="truncate uppercase font-semibold tracking-wide text-center w-full !text-white">
          {triggerLabel}
        </span>
        <span aria-hidden className="absolute right-4 text-white/80 shrink-0 text-base leading-none">
          ▾
        </span>
      </Button>
      <Popover className={`${popoverPage} min-w-[var(--trigger-width)]`} offset={0}>
        <div className="border-b border-[var(--border)] p-2">
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rechercher un scénario…"
            className={`${fieldInput} text-sm`}
            aria-label="Rechercher un scénario"
          />
        </div>
        <ListBox
          selectionMode="single"
          className={`${listBoxPage} w-full max-h-[min(24rem,70vh)] overflow-y-auto`}
        >
          <ListBoxItem
            id={ALL_SCENARIOS_KEY}
            textValue={ALL_SCENARIOS_LABEL}
            className={listBoxItemPage}
          >
            {ALL_SCENARIOS_LABEL}
          </ListBoxItem>

          {isSearching
            ? filteredScenarios.map((scenario) => renderSearchItem(scenario))
            : renderYearHierarchy()}
        </ListBox>
      </Popover>
    </Select>
  );
}
