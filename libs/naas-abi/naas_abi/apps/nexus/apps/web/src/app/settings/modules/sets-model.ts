/**
 * The sets of the modules × workspaces page: what an organization or a workspace may use, as
 * IAM records it (`SetParts`). Everything here is pure; the view holds a draft per column and
 * asks this file what a cell shows and what a click makes of the draft.
 *
 * Grammar of a module entry: `<module>` (the whole module), `<type>/<module>/<name>` (one agent,
 * app, workflow or pipeline; `*` for every item of the type) or `<service>:<Action>` (an action
 * the module declares). `null` is "nothing recorded": everything for an organization, whatever
 * its organization has for a workspace. `[]` is nothing.
 */
import type { ModuleScopeItem, ModuleScopesEntry, SetParts } from '@/lib/iam-admin/types';

export type ItemType = 'agent' | 'app' | 'workflow' | 'pipeline';

type ItemsKey = 'agents' | 'apps' | 'workflows' | 'pipelines';

export const ITEM_TYPES: { type: ItemType; key: ItemsKey; label: string }[] = [
  { type: 'agent', key: 'agents', label: 'Agents' },
  { type: 'app', key: 'apps', label: 'Apps' },
  { type: 'workflow', key: 'workflows', label: 'Workflows' },
  { type: 'pipeline', key: 'pipelines', label: 'Pipelines' },
];

/** The rows of the matrix: the modules and the deployment's features. */
export type SetCatalog = { modules: ModuleScopesEntry[]; features: string[] };

/** One row: a whole module, one of its items or declared actions, or a feature. */
export type SetRow =
  | { kind: 'module'; module: string }
  | { kind: 'item'; module: string; type: ItemType; name: string }
  | { kind: 'action'; module: string; action: string }
  | { kind: 'feature'; feature: string };

/** How much of a row a set holds: a module may be held in part (some of its items). */
export type Coverage = 'all' | 'some' | 'none';

export function itemEntry(type: ItemType, moduleId: string, name: string): string {
  return `${type}/${moduleId}/${name}`;
}

export function wildcardEntry(type: ItemType, moduleId: string): string {
  return itemEntry(type, moduleId, '*');
}

export function itemsOf(entry: ModuleScopesEntry, type: ItemType): ModuleScopeItem[] {
  const key = ITEM_TYPES.find((t) => t.type === type)!.key;
  return entry[key] ?? [];
}

/** The `<service>:<Action>` entries a module declares. */
export function declaredActions(entry: ModuleScopesEntry): string[] {
  return entry.declared?.actions.map((a) => a.action) ?? [];
}

function entryOf(catalog: SetCatalog, moduleId: string): ModuleScopesEntry | undefined {
  return catalog.modules.find((m) => m.module === moduleId);
}

const ITEM_PATTERN = /^(agent|app|workflow|pipeline)\/([^/]+)\/(.+)$/;

/** The module a set entry belongs to, when the catalog knows it. */
export function moduleOfEntry(item: string, catalog: SetCatalog): string | null {
  const match = ITEM_PATTERN.exec(item);
  if (match) return match[2];
  if (item.includes(':')) {
    const service = item.split(':', 1)[0];
    return catalog.modules.find((m) => m.declared?.service === service)?.module ?? null;
  }
  return item;
}

/** Whether a set entry is the module itself, one of its items or one of its declared actions. */
export function belongsTo(item: string, entry: ModuleScopesEntry): boolean {
  if (item === entry.module) return true;
  const match = ITEM_PATTERN.exec(item);
  if (match) return match[2] === entry.module;
  return declaredActions(entry).includes(item);
}

/** Whether a module list holds one entry (itself, through its module, or a `*`). */
export function listCovers(list: string[] | null, item: string, catalog: SetCatalog): boolean {
  if (list === null) return true;
  if (list.includes(item)) return true;
  const match = ITEM_PATTERN.exec(item);
  if (match) {
    const [, type, moduleId] = match;
    return list.includes(moduleId) || list.includes(wildcardEntry(type as ItemType, moduleId));
  }
  if (item.includes(':')) {
    const moduleId = moduleOfEntry(item, catalog);
    return moduleId !== null && list.includes(moduleId);
  }
  return false;
}

/** How much of a module a list holds: `<module>` is all of it, any item of it is some. */
export function moduleCoverage(list: string[] | null, entry: ModuleScopesEntry): Coverage {
  if (list === null || list.includes(entry.module)) return 'all';
  return list.some((item) => belongsTo(item, entry)) ? 'some' : 'none';
}

function rowEntry(row: Exclude<SetRow, { kind: 'module' } | { kind: 'feature' }>): string {
  return row.kind === 'item' ? itemEntry(row.type, row.module, row.name) : row.action;
}

/** How much of a row a set holds, as recorded (`null` parts hold everything). */
export function coverage(parts: SetParts, row: SetRow, catalog: SetCatalog): Coverage {
  if (row.kind === 'feature') {
    return parts.features === null || parts.features.includes(row.feature) ? 'all' : 'none';
  }
  if (row.kind === 'module') {
    const entry = entryOf(catalog, row.module);
    if (!entry) return parts.modules === null || parts.modules.includes(row.module) ? 'all' : 'none';
    return moduleCoverage(parts.modules, entry);
  }
  return listCovers(parts.modules, rowEntry(row), catalog) ? 'all' : 'none';
}

/**
 * What a column shows for a row. A workspace's `null` part is whatever its organization has, so
 * it shows the organization's (`bound`); an organization's (no bound) is everything.
 */
export function displayCoverage(
  parts: SetParts,
  bound: SetParts | null,
  row: SetRow,
  catalog: SetCatalog,
): Coverage {
  const part = row.kind === 'feature' ? 'features' : 'modules';
  if (parts[part] === null && bound) return coverage(bound, row, catalog);
  return coverage(parts, row, catalog);
}

/**
 * Whether a workspace may hold a row, given its organization's set (`bound`): a whole module
 * only when the organization has all of it, an item or an action when the organization has it.
 * An organization (no bound) may hold any row.
 */
export function withinBound(bound: SetParts | null, row: SetRow, catalog: SetCatalog): boolean {
  if (!bound) return true;
  return coverage(bound, row, catalog) === 'all';
}

/**
 * Whether a column records something of the row that its organization leaves out: shown, but
 * not effective. A `null` part follows the organization, so it never does.
 */
export function rowOutside(
  parts: SetParts,
  bound: SetParts | null,
  row: SetRow,
  catalog: SetCatalog,
): boolean {
  if (!bound) return false;
  if (row.kind === 'feature') {
    if (parts.features === null || bound.features === null) return false;
    return parts.features.includes(row.feature) && !bound.features.includes(row.feature);
  }
  const list = parts.modules;
  if (list === null || bound.modules === null) return false;
  if (row.kind === 'module') {
    const entry = entryOf(catalog, row.module);
    const mine = entry ? list.filter((item) => belongsTo(item, entry)) : list.filter((item) => item === row.module);
    return mine.some((item) => !listCovers(bound.modules, item, catalog));
  }
  const item = rowEntry(row);
  return listCovers(list, item, catalog) && !listCovers(bound.modules, item, catalog);
}

/**
 * What a workspace records that its organization leaves out, in the API's words (`crm`,
 * `agent/crm/Sales`, `feature files`): saving such a set is refused until they go.
 */
export function outsideOfBound(parts: SetParts, bound: SetParts | null, catalog: SetCatalog): string[] {
  if (!bound) return [];
  const out: string[] = [];
  if (parts.modules !== null && bound.modules !== null) {
    for (const item of parts.modules) if (!listCovers(bound.modules, item, catalog)) out.push(item);
  }
  if (parts.features !== null && bound.features !== null) {
    for (const feature of parts.features) if (!bound.features.includes(feature)) out.push(`feature ${feature}`);
  }
  return out;
}

/** A `null` modules part as explicit entries: the bound's, else every module whole. */
export function materialiseModules(parts: SetParts, bound: SetParts | null, catalog: SetCatalog): string[] {
  if (parts.modules !== null) return [...parts.modules];
  if (bound && bound.modules !== null) return [...bound.modules];
  return catalog.modules.map((m) => m.module);
}

/** A `null` features part as explicit features: the bound's, else every feature. */
export function materialiseFeatures(parts: SetParts, bound: SetParts | null, catalog: SetCatalog): string[] {
  if (parts.features !== null) return [...parts.features];
  if (bound && bound.features !== null) return [...bound.features];
  return [...catalog.features];
}

/** Both parts explicit (see `materialiseModules`, `materialiseFeatures`). */
export function materialise(parts: SetParts, bound: SetParts | null, catalog: SetCatalog): SetParts {
  return {
    modules: materialiseModules(parts, bound, catalog),
    features: materialiseFeatures(parts, bound, catalog),
  };
}

type Except = { type: ItemType; name: string } | { action: string } | null;

/**
 * A whole module as its items: `<type>/<module>/*` for each type it has, explicit names for the
 * type an item leaves, and each declared action, the one left out excepted.
 */
export function expandModule(entry: ModuleScopesEntry, except: Except = null): string[] {
  const out: string[] = [];
  for (const { type } of ITEM_TYPES) {
    const items = itemsOf(entry, type);
    if (!items.length) continue;
    if (except && 'type' in except && except.type === type) {
      for (const item of items) if (item.name !== except.name) out.push(itemEntry(type, entry.module, item.name));
    } else {
      out.push(wildcardEntry(type, entry.module));
    }
  }
  for (const action of declaredActions(entry)) {
    if (!(except && 'action' in except && except.action === action)) out.push(action);
  }
  return out;
}

function unique(list: string[]): string[] {
  return [...new Set(list)];
}

/** Every item of a type listed by name: one `*` instead. */
function collapse(list: string[], entry: ModuleScopesEntry, type: ItemType): string[] {
  const names = itemsOf(entry, type).map((item) => itemEntry(type, entry.module, item.name));
  if (!names.length || !names.every((name) => list.includes(name))) return list;
  return [...list.filter((item) => !names.includes(item)), wildcardEntry(type, entry.module)];
}

function toggleItem(
  list: string[],
  entry: ModuleScopesEntry,
  row: Extract<SetRow, { kind: 'item' }>,
  on: boolean,
  catalog: SetCatalog,
): string[] {
  const key = itemEntry(row.type, row.module, row.name);
  if (on) {
    if (listCovers(list, key, catalog)) return list;
    return collapse([...list, key], entry, row.type);
  }
  if (list.includes(entry.module)) {
    return unique([
      ...list.filter((item) => item !== entry.module && !belongsTo(item, entry)),
      ...expandModule(entry, { type: row.type, name: row.name }),
    ]);
  }
  const wildcard = wildcardEntry(row.type, row.module);
  if (list.includes(wildcard)) {
    const others = itemsOf(entry, row.type)
      .filter((item) => item.name !== row.name)
      .map((item) => itemEntry(row.type, row.module, item.name));
    return unique([...list.filter((item) => item !== wildcard && item !== key), ...others]);
  }
  return list.filter((item) => item !== key);
}

function toggleAction(list: string[], entry: ModuleScopesEntry, action: string, on: boolean): string[] {
  if (on) return list.includes(action) || list.includes(entry.module) ? list : [...list, action];
  if (list.includes(entry.module)) {
    return unique([
      ...list.filter((item) => item !== entry.module && !belongsTo(item, entry)),
      ...expandModule(entry, { action }),
    ]);
  }
  return list.filter((item) => item !== action);
}

/**
 * The set after checking (`on`) or unchecking a row. A `null` part is first made explicit (the
 * bound's, else everything); checking a module holds it whole and drops its items; unchecking one
 * item of a whole module lists the module's other items and actions instead.
 */
export function toggleRow(
  parts: SetParts,
  row: SetRow,
  on: boolean,
  catalog: SetCatalog,
  bound: SetParts | null = null,
): SetParts {
  if (row.kind === 'feature') {
    const features = materialiseFeatures(parts, bound, catalog).filter((f) => f !== row.feature);
    if (on) features.push(row.feature);
    const order = (f: string) => {
      const index = catalog.features.indexOf(f);
      return index < 0 ? catalog.features.length : index;
    };
    return { ...parts, features: features.sort((a, b) => order(a) - order(b)) };
  }
  const list = materialiseModules(parts, bound, catalog);
  const entry = entryOf(catalog, row.module);
  if (row.kind === 'module') {
    const kept = list.filter((item) => (entry ? !belongsTo(item, entry) : item !== row.module));
    return { ...parts, modules: on ? [...kept, row.module] : kept };
  }
  if (!entry) return { ...parts, modules: list };
  const modules =
    row.kind === 'item' ? toggleItem(list, entry, row, on, catalog) : toggleAction(list, entry, row.action, on);
  return { ...parts, modules };
}

function sameList(a: string[] | null, b: string[] | null): boolean {
  if (a === null || b === null) return a === b;
  const left = new Set(a);
  const right = new Set(b);
  return left.size === right.size && [...left].every((item) => right.has(item));
}

/** Whether two sets record the same (order does not count). */
export function sameParts(a: SetParts, b: SetParts): boolean {
  return sameList(a.modules, b.modules) && sameList(a.features, b.features);
}

/** A part in a few words: `Everything`, `Nothing`, or how many modules or features it holds. */
export function partSummary(
  parts: SetParts,
  part: 'modules' | 'features',
  catalog: SetCatalog,
): string {
  const list = parts[part];
  if (list === null) return 'Everything';
  if (part === 'features') {
    return list.length === 0 ? 'Nothing' : `${list.length} of ${catalog.features.length}`;
  }
  const held = catalog.modules.filter((entry) => moduleCoverage(list, entry) !== 'none').length;
  return list.length === 0 ? 'Nothing' : `${held} of ${catalog.modules.length}`;
}

/** Whether a module (its id, items or declared actions) matches a filter, ignoring case. */
export function moduleMatches(entry: ModuleScopesEntry, filter: string): boolean {
  const needle = filter.trim().toLowerCase();
  if (!needle) return true;
  const words = [
    entry.module,
    ...ITEM_TYPES.flatMap(({ type }) => itemsOf(entry, type).flatMap((item) => [item.name, item.display_name])),
    ...declaredActions(entry),
  ];
  return words.some((word) => word.toLowerCase().includes(needle));
}
