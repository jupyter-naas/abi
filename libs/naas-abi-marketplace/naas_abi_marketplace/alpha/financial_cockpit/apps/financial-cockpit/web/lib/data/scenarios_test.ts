import {
  filterScenariosByQuery,
  groupScenarios,
  groupScenariosByYear,
  ALL_SCENARIOS_SCENARIO_ID,
  resolveActiveScenario,
  resolveCurrentYearScenario,
  type ScenarioOption,
} from '@/lib/data/scenarios';
import { filterByScenario } from '@/lib/data/filter';

const sampleScenarios: ScenarioOption[] = [
  { id: '2026-02', label: 'Février 2026', split: 'date_month' },
  { id: '2026-01', label: 'Janvier 2026', split: 'date_month' },
  { id: '2026', label: '2026', split: 'date_year' },
  { id: '2025', label: '2025', split: 'date_year' },
];

describe('groupScenariosByYear', () => {
  it('nests months under preprocessed year options', () => {
    const grouped = groupScenariosByYear(sampleScenarios);
    expect(grouped.map((group) => group.yearId)).toEqual(['2026', '2025']);
    expect(grouped[0].months.map((month) => month.id)).toEqual(['2026-02', '2026-01']);
    expect(grouped[0].year.split).toBe('date_year');
  });
});

describe('groupScenarios', () => {
  it('groups preprocessed month and year options', () => {
    const grouped = groupScenarios(sampleScenarios);
    expect(grouped.date_month.map((scenario) => scenario.id)).toEqual(['2026-02', '2026-01']);
    expect(grouped.date_year.map((scenario) => scenario.id)).toEqual(['2026', '2025']);
  });
});

describe('resolveActiveScenario', () => {
  const referenceDate = new Date('2026-06-01');

  it('accepts known ids and rejects unknown ones', () => {
    expect(resolveActiveScenario('2026', sampleScenarios, referenceDate)?.split).toBe(
      'date_year',
    );
    expect(resolveActiveScenario('2026-01', sampleScenarios, referenceDate)?.split).toBe(
      'date_month',
    );
    expect(resolveActiveScenario('1999', sampleScenarios, referenceDate)).toBeNull();
    expect(resolveActiveScenario(ALL_SCENARIOS_SCENARIO_ID, sampleScenarios, referenceDate)).toBeNull();
  });

  it('defaults to the current calendar year when no scenario is selected', () => {
    expect(resolveActiveScenario(null, sampleScenarios, referenceDate)?.id).toBe('2026');
    expect(resolveActiveScenario(undefined, sampleScenarios, referenceDate)?.id).toBe('2026');
    expect(resolveCurrentYearScenario(sampleScenarios, referenceDate)?.id).toBe('2026');
  });
});

describe('filterScenariosByQuery', () => {
  it('filters by label, id, and group label', () => {
    expect(filterScenariosByQuery(sampleScenarios, 'février').map((s) => s.id)).toEqual([
      '2026-02',
    ]);
    expect(filterScenariosByQuery(sampleScenarios, 'année').map((s) => s.id)).toEqual([
      '2026',
      '2025',
    ]);
  });
});

describe('filterByScenario', () => {
  it('filters records by preprocessed month or year fields', () => {
    const records = [
      { invoice_id: '1', scenario: '2026-01', scenario_year: '2026' },
      { invoice_id: '2', scenario: '2025-12', scenario_year: '2025' },
    ];
    expect(filterByScenario(records, '2026-01', 'date_month')).toEqual([records[0]]);
    expect(filterByScenario(records, '2026', 'date_year')).toEqual([records[0]]);
    expect(filterByScenario(records, null, null)).toEqual(records);
  });
});
