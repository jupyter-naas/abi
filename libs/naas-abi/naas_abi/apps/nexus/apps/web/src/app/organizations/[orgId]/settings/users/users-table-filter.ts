import {
  conditionsOf,
  isBlank,
  type ColumnCondition,
  type ColumnFilterState,
} from '@/lib/graph-query/filters';
import type { Operator } from '@/lib/graph-query/types';

function needleOf(value: ColumnCondition['value']): string {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value).toLowerCase()
    : '';
}

function matchesCondition(cell: string, cond: ColumnCondition): boolean {
  const hay = cell.toLowerCase();
  const needle = needleOf(cond.value);
  const op: Operator = cond.operator;
  if (op === 'isEmpty') return cell.trim() === '';
  if (op === 'isNotEmpty') return cell.trim() !== '';
  if (op === 'eq') return hay === needle;
  if (op === 'neq') return hay !== needle;
  if (op === 'contains') return hay.includes(needle);
  if (op === 'notContains') return !hay.includes(needle);
  if (op === 'startsWith') return hay.startsWith(needle);
  if (op === 'endsWith') return hay.endsWith(needle);
  return hay.includes(needle);
}

/** A row matches when any of its cell strings satisfy the Excel column filter. */
export function rowMatchesColumnFilter(
  cellValues: string[],
  state: ColumnFilterState | undefined
): boolean {
  if (isBlank(state)) return true;
  const values = cellValues.length > 0 ? cellValues : [''];
  const selected = state?.selected ?? [];
  if (selected.length > 0 && !values.some((value) => selected.includes(value))) {
    return false;
  }
  const conds = conditionsOf(state);
  if (conds.length === 0) return true;
  const hit = (cond: ColumnCondition) =>
    values.some((value) => matchesCondition(value, cond));
  return (state?.combinator ?? 'and') === 'or'
    ? conds.some(hit)
    : conds.every(hit);
}
