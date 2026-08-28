"use client";

import type { QueryEntry, Scenario } from "@/lib/types";

type Props = {
  scenarios: Scenario[];
  queries: QueryEntry[];
  scenarioId: string;
  querySlug: string;
  onScenarioChange: (id: string) => void;
  onQueryChange: (slug: string) => void;
};

export function Filters({
  scenarios,
  queries,
  scenarioId,
  querySlug,
  onScenarioChange,
  onQueryChange,
}: Props) {
  return (
    <div className="controls">
      <div className="field">
        <label htmlFor="window-select">Scenario</label>
        <select
          id="window-select"
          value={scenarioId}
          onChange={(e) => onScenarioChange(e.target.value)}
        >
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="query-select">Query</label>
        <select
          id="query-select"
          className="query-select"
          value={querySlug}
          onChange={(e) => onQueryChange(e.target.value)}
        >
          {queries.map((q) => (
            <option key={q.slug} value={q.slug}>
              {q.query}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
