/**
 * Notion-style database model shared by every Nexus database surface (Apps,
 * Board, …).
 *
 * A surface describes its rows once — a list of properties, each reading the
 * display values of a row — and gets filtering, search, sorting and grouping
 * for free. Views (gallery, table, list, board) only ever read the property
 * values, so they work the same whatever the row type is.
 */

// ---------------------------------------------------------------------------
// Properties
// ---------------------------------------------------------------------------

/** `title` is the row name — always visible, never hideable. */
export type PropertyType = 'title' | 'text' | 'select' | 'multi' | 'url' | 'date' | 'person';

export interface PropertyDef<R, K extends string = string> {
  key: K;
  label: string;
  type: PropertyType;
  /** Display values of the property on a row; empty array when unset. */
  values: (record: R) => string[];
  /**
   * Known values in their natural order (stages, priorities). Sorting follows
   * this order instead of the alphabet, and grouping lists every option, even
   * the ones no row has yet.
   */
  options?: string[];
  /** Raw value to sort on when the display value does not sort (dates). */
  sortValue?: (record: R) => string;
}

export type FilterOperator =
  | 'is'
  | 'is_not'
  | 'contains'
  | 'not_contains'
  | 'is_empty'
  | 'is_not_empty';

export interface Filter<K extends string = string> {
  id: string;
  property: K;
  operator: FilterOperator;
  value: string;
}

export interface SortRule<K extends string = string> {
  property: K;
  direction: 'asc' | 'desc';
}

export interface ViewConfig<K extends string = string, T extends string = string> {
  id: string;
  name: string;
  type: T;
  /** Ordered list of properties shown besides the title. */
  visible: K[];
  filters: Filter<K>[];
  sort: SortRule<K> | null;
  groupBy: K | null;
}

export interface RecordGroup<R> {
  key: string;
  label: string;
  records: R[];
}

export const FILTER_OPERATOR_LABELS: Record<FilterOperator, string> = {
  is: 'is',
  is_not: 'is not',
  contains: 'contains',
  not_contains: 'does not contain',
  is_empty: 'is empty',
  is_not_empty: 'is not empty',
};

export function isBoundedType(type: PropertyType): boolean {
  return type === 'select' || type === 'multi' || type === 'person';
}

export function operatorsFor(type: PropertyType): FilterOperator[] {
  if (type === 'select') return ['is', 'is_not', 'is_empty', 'is_not_empty'];
  return ['contains', 'not_contains', 'is', 'is_not', 'is_empty', 'is_not_empty'];
}

export function operatorNeedsValue(operator: FilterOperator): boolean {
  return operator !== 'is_empty' && operator !== 'is_not_empty';
}

const compareText = (a: string, b: string) => a.localeCompare(b, undefined, { sensitivity: 'base' });

// ---------------------------------------------------------------------------
// Schema: properties + the query pipeline bound to them
// ---------------------------------------------------------------------------

export interface DatabaseSchema<R, K extends string> {
  properties: PropertyDef<R, K>[];
  propertyByKey: Record<K, PropertyDef<R, K>>;
  /** The property holding the row name. */
  titleKey: K;
  /** Every property but the title: the ones a view can show, hide and filter on. */
  optionalProperties: PropertyDef<R, K>[];
  /** Properties with a bounded set of values, plus dates (one group per day). */
  groupableProperties: PropertyDef<R, K>[];
  propertyValues: (record: R, key: K) => string[];
  /** Single display string for a property ("—" is left to the renderer). */
  propertyText: (record: R, key: K) => string;
  /** Distinct values seen for a property across rows; option order when known. */
  facetValues: (records: R[], key: K) => string[];
  applyFilters: (records: R[], filters: Filter<K>[]) => R[];
  applySearch: (records: R[], search: string) => R[];
  applySort: (records: R[], sort: SortRule<K> | null) => R[];
  /**
   * Split rows by a property. Multi-value properties place a row in every
   * matching group, like Notion does. Rows without a value land in a trailing
   * "No <property>" group. Groups follow the property's option order, else
   * its sort value (dates chronologically), else the alphabet; ``direction``
   * 'desc' reverses that order (the empty group stays last).
   */
  groupRecords: (records: R[], groupBy: K | null, direction?: 'asc' | 'desc') => RecordGroup<R>[];
}

export function createSchema<R, K extends string>(
  properties: PropertyDef<R, K>[],
): DatabaseSchema<R, K> {
  const propertyByKey = properties.reduce(
    (acc, def) => ({ ...acc, [def.key]: def }),
    {} as Record<K, PropertyDef<R, K>>,
  );
  const title = properties.find((p) => p.type === 'title');
  if (!title) throw new Error('A database schema needs a title property');
  const titleKey = title.key;

  const propertyValues = (record: R, key: K) => propertyByKey[key].values(record);
  const propertyText = (record: R, key: K) => propertyValues(record, key).join(', ');

  const facetValues = (records: R[], key: K) => {
    const seen = new Set<string>();
    for (const record of records) {
      for (const value of propertyValues(record, key)) seen.add(value);
    }
    const options = propertyByKey[key].options;
    if (options) {
      return [...options.filter((o) => seen.has(o)), ...Array.from(seen).filter((v) => !options.includes(v)).sort(compareText)];
    }
    return Array.from(seen).sort(compareText);
  };

  const matchesFilter = (record: R, filter: Filter<K>) => {
    const values = propertyValues(record, filter.property);
    const needle = filter.value.trim().toLowerCase();
    switch (filter.operator) {
      case 'is_empty':
        return values.length === 0;
      case 'is_not_empty':
        return values.length > 0;
      case 'is':
        return values.some((v) => v.toLowerCase() === needle);
      case 'is_not':
        return !values.some((v) => v.toLowerCase() === needle);
      case 'contains':
        return values.some((v) => v.toLowerCase().includes(needle));
      case 'not_contains':
        return !values.some((v) => v.toLowerCase().includes(needle));
    }
  };

  const applyFilters = (records: R[], filters: Filter<K>[]) => {
    const active = filters.filter(
      (f) => f.property in propertyByKey && (!operatorNeedsValue(f.operator) || f.value.trim() !== ''),
    );
    if (active.length === 0) return records;
    return records.filter((record) => active.every((filter) => matchesFilter(record, filter)));
  };

  const applySearch = (records: R[], search: string) => {
    const q = search.trim().toLowerCase();
    if (!q) return records;
    return records.filter((record) =>
      properties.some((def) => def.values(record).some((v) => v.toLowerCase().includes(q))),
    );
  };

  // Option order, raw sort value, then display text.
  const sortKey = (record: R, def: PropertyDef<R, K>): string | number => {
    if (def.sortValue) return def.sortValue(record);
    const text = propertyText(record, def.key);
    if (def.options && text) {
      const index = def.options.indexOf(propertyValues(record, def.key)[0]);
      if (index >= 0) return index;
    }
    return text;
  };

  const applySort = (records: R[], sort: SortRule<K> | null) => {
    const rule = sort && sort.property in propertyByKey ? sort : { property: titleKey, direction: 'asc' as const };
    const def = propertyByKey[rule.property];
    return [...records].sort((a, b) => {
      const left = sortKey(a, def);
      const right = sortKey(b, def);
      // Rows missing the sort property sink to the bottom in either direction.
      if (left === '' && right !== '') return 1;
      if (left !== '' && right === '') return -1;
      const cmp =
        typeof left === 'number' && typeof right === 'number'
          ? left - right
          : compareText(String(left), String(right));
      if (cmp !== 0) return rule.direction === 'asc' ? cmp : -cmp;
      return compareText(propertyText(a, titleKey), propertyText(b, titleKey));
    });
  };

  const groupRecords = (records: R[], groupBy: K | null, direction: 'asc' | 'desc' = 'asc'): RecordGroup<R>[] => {
    if (!groupBy || !(groupBy in propertyByKey)) return [{ key: '__all__', label: '', records }];
    const def = propertyByKey[groupBy];

    const groups = new Map<string, R[]>();
    for (const option of def.options ?? []) groups.set(option, []);
    const empty: R[] = [];
    for (const record of records) {
      const values = propertyValues(record, groupBy);
      if (values.length === 0) {
        empty.push(record);
        continue;
      }
      for (const value of values) {
        const bucket = groups.get(value);
        if (bucket) bucket.push(record);
        else groups.set(value, [record]);
      }
    }

    const entries = Array.from(groups.entries());
    const options = def.options;
    if (options) {
      entries.sort(([a], [b]) => {
        const ia = options.indexOf(a);
        const ib = options.indexOf(b);
        if (ia >= 0 && ib >= 0) return ia - ib;
        if (ia >= 0) return -1;
        if (ib >= 0) return 1;
        return compareText(a, b);
      });
    } else if (def.sortValue) {
      const sortValue = def.sortValue;
      entries.sort(([, a], [, b]) => compareText(sortValue(a[0]), sortValue(b[0])));
    } else {
      entries.sort(([a], [b]) => compareText(a, b));
    }
    if (direction === 'desc') entries.reverse();
    const result: RecordGroup<R>[] = entries.map(([key, groupedRecords]) => ({
      key,
      label: key,
      records: groupedRecords,
    }));

    if (empty.length > 0) {
      result.push({ key: '__empty__', label: `No ${def.label.toLowerCase()}`, records: empty });
    }
    return result;
  };

  const optionalProperties = properties.filter((p) => p.type !== 'title');
  return {
    properties,
    propertyByKey,
    titleKey,
    optionalProperties,
    groupableProperties: properties.filter((p) => isBoundedType(p.type) || p.type === 'date'),
    propertyValues,
    propertyText,
    facetValues,
    applyFilters,
    applySearch,
    applySort,
    groupRecords,
  };
}
