'use client';

import type { DivisionSummary } from '@/lib/pilotage/costCenters/model';
import { Treemap as BaseTreemap } from '@/components/dashboard/viz/Treemap';

type TreemapProps = {
  title: string;
  hint?: string;
  divisions: DivisionSummary[];
  emptyMessage?: string;
};

/**
 * Cost-center spend as a treemap: divisions are the groups, cost centers the
 * tiles inside them. The layout itself lives in the shared `Treemap`; this only
 * maps the cost-center shape onto it.
 */
export function Treemap({
  title,
  hint,
  divisions,
  emptyMessage = 'No spend for this perimeter.',
}: TreemapProps) {
  return (
    <BaseTreemap
      title={title}
      hint={hint}
      emptyMessage={emptyMessage}
      groups={divisions.map((division) => ({
        key: division.key,
        label: division.label,
        value: division.actual,
        leaves: division.centers.map((center) => ({
          key: center.key,
          label: center.label,
          value: center.actual,
        })),
      }))}
    />
  );
}
