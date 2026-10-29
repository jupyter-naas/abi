/**
 * The policy builder's logic, apart from the screen. It starts from what the caller may grant
 * at the scope (`GET /grantable?scope=`, already within the scope's sets) and offers it as
 * checkboxes: per module its agents, apps, workflows, pipelines and declared actions, and the
 * Nexus features. A choice is written as Allow statements on `${scope}/` resources, and a
 * document is read back into choices, what the builder cannot show kept as statements.
 */
import type { GrantableView, ModuleScopeItem, ModuleScopesEntry, PolicyStatement } from '@/lib/iam-admin/types';
import { featureLabel, sortFeaturesByName } from '@/lib/feature-labels';

export type BuilderItem = {
  key: string;
  label: string;
  description: string;
  icon: string | null;
  /** What choosing it grants: the item's actions the caller holds on its resource. */
  actions: string[];
  resource: string;
};

export type BuilderSectionId = 'agents' | 'apps' | 'workflows' | 'pipelines' | 'actions' | 'features';

export type BuilderSection = { id: BuilderSectionId; label: string; items: BuilderItem[] };

export type BuilderGroup = { id: string; label: string; kind: 'module' | 'nexus'; sections: BuilderSection[] };

/** What a pattern written at the scope starts with: what the scope's container holds. */
const SCOPE_PREFIX = '${scope}/';

const FEATURE_PREFIX = `${SCOPE_PREFIX}nexus:feature/`;

/** A pattern written at a scope (`${scope}` or `${scope}/...`) as it reads at ``scope``: a
 *  container's name, the platform `abi:` (where `${scope}/` reads `abi:`), or below a
 *  container (`<container>/*`), read at the container itself. */
export function atScope(pattern: string, scope: string): string {
  const container = scope.endsWith('/*') ? scope.slice(0, -2) : scope;
  if (pattern.startsWith(SCOPE_PREFIX)) {
    const rest = pattern.slice(SCOPE_PREFIX.length);
    return container === 'abi:' ? `abi:${rest}` : `${container}/${rest}`;
  }
  return pattern === '${scope}' ? container : pattern;
}

/** IAM's glob (core `names.matches`): `*` any run of characters, `?` one, the rest as is. */
export function globMatches(pattern: string, value: string): boolean {
  if (pattern === '*') return true;
  if (!pattern.includes('*') && !pattern.includes('?')) return pattern === value;
  const regex = pattern
    .split('')
    .map((char) => (char === '*' ? '.*' : char === '?' ? '.' : char.replace(/[.+^${}()|[\]\\]/g, '\\$&')))
    .join('');
  return new RegExp(`^${regex}$`, 's').test(value);
}

type Holdings = Map<string, { resources: string[]; excluded: string[] }>;

function holdings(grantable: GrantableView): Holdings {
  const held: Holdings = new Map();
  for (const catalog of grantable.catalogs) {
    for (const a of catalog.actions) held.set(a.action, { resources: a.resources, excluded: a.excluded });
  }
  return held;
}

/** The actions of ``actions`` the caller may grant on ``resource``: held on a pattern that
 *  covers it, and no Deny of theirs touching it. */
function heldOf(held: Holdings, actions: string[], resource: string): string[] {
  return actions.filter((action) => {
    const found = held.get(action);
    if (!found || !found.resources.some((p) => globMatches(p, resource))) return false;
    return !found.excluded.some((d) => globMatches(d, resource) || globMatches(resource, d));
  });
}

const byLabel = (a: BuilderItem, b: BuilderItem) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' });

function itemsOf(held: Holdings, items: ModuleScopeItem[]): BuilderItem[] {
  return items
    .flatMap((item) => {
      const actions = heldOf(held, item.actions, item.resource);
      if (!actions.length) return [];
      return [
        {
          key: item.resource.startsWith(SCOPE_PREFIX) ? item.resource.slice(SCOPE_PREFIX.length) : item.resource,
          label: item.display_name || item.name,
          description: item.description,
          icon: item.icon,
          actions,
          resource: item.resource,
        },
      ];
    })
    .sort(byLabel);
}

function declaredItems(held: Holdings, declared: NonNullable<ModuleScopesEntry['declared']>): BuilderItem[] {
  return declared.actions
    .flatMap((spec) =>
      spec.resource_types.flatMap((type) => {
        const resource =
          declared.resource_types.find((t) => t.name === type)?.resource ?? `${SCOPE_PREFIX}${declared.service}:${type}/*`;
        if (!heldOf(held, [spec.action], resource).length) return [];
        const name = spec.action.split(':')[1] ?? spec.action;
        return [
          {
            key: `declared:${spec.action}@${resource}`,
            label: spec.resource_types.length > 1 ? `${name} (${type})` : name,
            description: spec.description,
            icon: null,
            actions: [spec.action],
            resource,
          },
        ];
      }),
    )
    .sort(byLabel);
}

/** The features to offer: the known ones, and any a grantable pattern names. */
function featureKeys(held: Holdings, known: string[]): string[] {
  const named = (held.get('nexus:UseFeature')?.resources ?? [])
    .filter((p) => p.startsWith(FEATURE_PREFIX) && !/[*?]/.test(p))
    .map((p) => p.slice(FEATURE_PREFIX.length));
  return sortFeaturesByName([...new Set([...known, ...named])]);
}

/** What the builder offers: one group per module with something grantable, then Nexus features. */
export function builderGroups(grantable: GrantableView, modules: ModuleScopesEntry[], features: string[]): BuilderGroup[] {
  const held = holdings(grantable);
  const groups: BuilderGroup[] = [];
  for (const entry of modules) {
    const sections: BuilderSection[] = [
      { id: 'agents' as const, label: 'Agents', items: itemsOf(held, entry.agents) },
      { id: 'apps' as const, label: 'Apps', items: itemsOf(held, entry.apps) },
      { id: 'workflows' as const, label: 'Workflows', items: itemsOf(held, entry.workflows) },
      { id: 'pipelines' as const, label: 'Pipelines', items: itemsOf(held, entry.pipelines) },
      { id: 'actions' as const, label: 'Actions', items: entry.declared ? declaredItems(held, entry.declared) : [] },
    ].filter((section) => section.items.length > 0);
    if (sections.length) groups.push({ id: entry.module, label: entry.module, kind: 'module', sections });
  }
  const featureItems = featureKeys(held, features).flatMap((key) => {
    const resource = `${FEATURE_PREFIX}${key}`;
    const actions = heldOf(held, ['nexus:UseFeature'], resource);
    return actions.length ? [{ key: `feature:${key}`, label: featureLabel(key), description: '', icon: null, actions, resource }] : [];
  });
  if (featureItems.length) {
    groups.push({ id: 'nexus', label: 'Nexus features', kind: 'nexus', sections: [{ id: 'features', label: 'Features', items: featureItems }] });
  }
  return groups;
}

function allItems(groups: BuilderGroup[]): BuilderItem[] {
  return groups.flatMap((g) => g.sections.flatMap((s) => s.items));
}

const actionsKey = (actions: string[]) => [...actions].sort().join(',');

const SID_MAX = 64;

/** A statement's sid from its actions, service included (`module:UseAgent` → `ModuleUseAgent`):
 *  IAM takes 1 to 64 letters and digits. */
function sidOf(actions: string[]): string {
  const words = actions.flatMap((a) => a.split(/[^A-Za-z0-9]+/)).filter(Boolean);
  const sid = words.map((w) => w[0].toUpperCase() + w.slice(1)).join('');
  return (sid || 'Builder').slice(0, SID_MAX);
}

/** ``base``, or ``base2``, ``base3``…, the first not in ``taken`` (IAM refuses a sid twice). */
function uniqueSid(base: string, taken: Set<string>): string {
  let sid = base;
  for (let n = 2; taken.has(sid); n += 1) {
    const suffix = String(n);
    sid = base.slice(0, SID_MAX - suffix.length) + suffix;
  }
  taken.add(sid);
  return sid;
}

/**
 * The choices as statements: one Allow per set of actions, in the order they are offered.
 * Each sid names its actions with their services and is unique, among these and the sids of
 * ``kept`` (the statements the builder cannot show, which stay in the policy).
 */
export function builderStatements(
  groups: BuilderGroup[],
  selected: ReadonlySet<string>,
  kept: PolicyStatement[] = [],
): PolicyStatement[] {
  const statements = new Map<string, PolicyStatement>();
  const taken = new Set(kept.flatMap((s) => (s.sid ? [s.sid] : [])));
  for (const item of allItems(groups)) {
    if (!selected.has(item.key)) continue;
    const key = actionsKey(item.actions);
    const found = statements.get(key);
    if (found) found.resources.push(item.resource);
    else {
      const sid = uniqueSid(sidOf(item.actions), taken);
      statements.set(key, { sid, effect: 'Allow', actions: [...item.actions], resources: [item.resource] });
    }
  }
  return [...statements.values()];
}

/**
 * A document read back into choices: an Allow whose every resource is an item granted with
 * exactly that item's actions is chosen; any other statement (a Deny, other actions, part of
 * an item's actions, a resource the builder does not offer) is kept as it is, in ``rest``.
 */
export function splitStatements(
  groups: BuilderGroup[],
  statements: PolicyStatement[],
): { selected: Set<string>; rest: PolicyStatement[] } {
  const items = new Map(allItems(groups).map((item) => [`${actionsKey(item.actions)} ${item.resource}`, item]));
  const selected = new Set<string>();
  const rest: PolicyStatement[] = [];
  for (const statement of statements) {
    const key = actionsKey(statement.actions);
    const found = statement.resources.map((r) => items.get(`${key} ${r}`));
    if (statement.effect === 'Allow' && found.length > 0 && found.every(Boolean)) {
      for (const item of found) selected.add(item!.key);
    } else {
      rest.push(statement);
    }
  }
  return { selected, rest };
}

const REFUSAL = /allows (\S+) on (\S+?)(?: at (\S+))?, and /;

/** The items an IAM refusal names ("You cannot grant what you do not hold: … allows <action>
 *  on <resource> at <scope>, and …"), whether the resource is written `${scope}/` or placed. */
export function refusedItems(groups: BuilderGroup[], message: string, scope: string): string[] {
  const match = REFUSAL.exec(message);
  if (!match) return [];
  const [, action, resource, at] = match;
  const placedAt = at ?? scope;
  return allItems(groups)
    .filter(
      (item) =>
        item.actions.includes(action) &&
        (item.resource === resource || atScope(item.resource, placedAt) === resource),
    )
    .map((item) => item.key);
}
