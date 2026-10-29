/**
 * The policy builder's logic, apart from the screen. It starts from what the caller may grant
 * at the scope, by publisher (`GET /publishers?scope=&parent=`: the engine, naas_abi, then the
 * modules, each with only what the caller may grant there, within the parent of a sub-policy)
 * and offers, per resource type, its actions and then its resources: picked from the listing
 * (`GET /resources`) or written as a wildcard under `${scope}/`. Each type's choice is written
 * as one Allow statement, and a document is read back into choices, what the builder cannot
 * show kept as statements.
 */
import type { PolicyStatement, PublishedAction, PublishedType, Publisher, PublishersView } from '@/lib/iam-admin/types';

/** One resource type of a publisher, as the builder offers it. */
export type BuilderType = {
  /** `<service>:<type>`, or `module:<type>@<module>` for a module's agents, apps, ... */
  key: string;
  service: string;
  type: string;
  /** The `module` catalog under a module: that module. */
  module: string | null;
  label: string;
  description: string;
  container: boolean;
  /** Its existing resources are listed; false: written as wildcards only. */
  listed: boolean;
  /** The actions the caller may grant of it, in the catalog's order. */
  actions: PublishedAction[];
  /** The last step of a name of this type: `<service>:<type>/`, a module's
   *  `module:<type>/<module>/`. */
  marker: string;
  /** What the caller may grant of it, every action together (`${scope}/...`). */
  patterns: string[];
};

export type BuilderPublisher = { id: string; kind: Publisher['kind']; label: string; types: BuilderType[] };

/** What the builder has chosen for one type: the actions, and the resources they are on. */
export type Choice = { actions: string[]; resources: string[] };

/** The choices by type key. */
export type Choices = Record<string, Choice>;

/** What a pattern written at the scope starts with: what the scope's container holds. */
const SCOPE_PREFIX = '${scope}/';
const SCOPE = '${scope}';

const PUBLISHER_RANK: Record<string, number> = { engine: 0, naas_abi: 1 };
const PUBLISHER_LABELS: Record<string, string> = { engine: 'Engine', naas_abi: 'naas_abi' };

/** What a module exposes, by its `module` catalog type. */
const MODULE_LABELS: Record<string, string> = { agent: 'Agents', app: 'Apps', workflow: 'Workflows', pipeline: 'Pipelines' };

function plural(word: string): string {
  if (/[^s]s$/.test(word)) return word;
  if (/[^aeiou]y$/.test(word)) return `${word.slice(0, -1)}ies`;
  if (/(s|x|ch|sh)$/.test(word)) return `${word}es`;
  return `${word}s`;
}

/** A type's name in the builder: a module's items by kind, the rest its type in the plural
 *  (`graph` → Graphs, `policy` → Policies). */
export function typeLabel(service: string, type: string): string {
  if (service === 'module' && MODULE_LABELS[type]) return MODULE_LABELS[type];
  const words = plural(type).replace(/_/g, ' ');
  return words[0].toUpperCase() + words.slice(1);
}

export function typeKey(type: Pick<PublishedType, 'service' | 'type' | 'module'>): string {
  return type.module ? `${type.service}:${type.type}@${type.module}` : `${type.service}:${type.type}`;
}

/** An id as one segment of a name, as IAM encodes it (`names.encode_segment`). */
function encodeSegment(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

function builderType(type: PublishedType): BuilderType {
  const step = `${type.service}:${type.type}/`;
  return {
    key: typeKey(type),
    service: type.service,
    type: type.type,
    module: type.module,
    label: typeLabel(type.service, type.type),
    description: type.description,
    container: type.container,
    listed: type.listed,
    actions: type.actions,
    marker: type.module ? `${step}${encodeSegment(type.module)}/` : step,
    patterns: [...new Set(type.actions.flatMap((a) => a.resources))],
  };
}

/** What the builder offers: the publishers in their order (the engine, naas_abi, then the
 *  modules by key), each with its types the caller may grant something of. */
export function builderPublishers(view: PublishersView): BuilderPublisher[] {
  return view.publishers
    .map((publisher) => ({
      id: publisher.id,
      kind: publisher.kind,
      label: PUBLISHER_LABELS[publisher.id] ?? publisher.id,
      types: publisher.types.filter((t) => t.actions.length > 0).map(builderType),
    }))
    .filter((publisher) => publisher.types.length > 0)
    .sort((a, b) => (PUBLISHER_RANK[a.id] ?? 2) - (PUBLISHER_RANK[b.id] ?? 2) || a.id.localeCompare(b.id));
}

export function allTypes(publishers: BuilderPublisher[]): BuilderType[] {
  return publishers.flatMap((p) => p.types);
}

// -- resources -----------------------------------------------------------------------------

/** A resource named canonically (`<container>/<service>:<type>/<id>`, as the listing names it)
 *  written at ``scope``: `${scope}/...` under it, `${scope}` the container itself, else as is. */
export function scopedName(name: string, scope: string): string {
  const container = scope.endsWith('/*') ? scope.slice(0, -2) : scope;
  if (name === container) return SCOPE;
  const under = container === 'abi:' ? 'abi:' : `${container}/`;
  return name.startsWith(under) ? SCOPE_PREFIX + name.slice(under.length) : name;
}

/** Whether ``resource`` (written at the scope) names resources of ``type``: its last step is the
 *  type's, or it is one of the patterns the caller may grant of it. */
export function belongsTo(type: BuilderType, resource: string): boolean {
  if (type.patterns.includes(resource)) return true;
  if (!resource.startsWith(SCOPE_PREFIX)) return false;
  const at = resource.lastIndexOf(type.marker);
  if (at < 0) return false;
  // The step must be at the start of what the scope holds or after a `/`.
  if (at !== SCOPE_PREFIX.length && resource[at - 1] !== '/') return false;
  // Nothing of another type after it: an id holds no `:` (IAM encodes it).
  return !resource.slice(at + type.marker.length).includes(':');
}

/** Whether the caller may grant something of ``type`` on ``resource`` (written at the scope):
 *  a listed resource is offered only then, so a sub-policy lists only what its parent has. */
export function grantableOn(type: BuilderType, resource: string): boolean {
  return type.actions.some(
    (a) => a.resources.some((p) => globMatches(p, resource)) && !a.excluded.some((d) => globMatches(d, resource)),
  );
}

/** Why a wildcard typed after `${scope}/` is not one of ``type``'s, or null. */
export function wildcardProblem(type: BuilderType, typed: string): string | null {
  const text = typed.trim();
  if (!text) return `Write a pattern after \${scope}/, such as ${type.marker}*`;
  if (/\s/.test(text)) return 'A pattern has no spaces.';
  if (!belongsTo(type, SCOPE_PREFIX + text)) return `A pattern of ${type.label.toLowerCase()} ends with ${type.marker}<id>, such as ${type.marker}*`;
  return null;
}

// -- statements ------------------------------------------------------------------------------

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
 * The choices as statements: one Allow per type with actions and resources chosen, in the order
 * the types are offered, its actions in the type's order. Each sid names its actions with their
 * services and is unique, among these and the sids of ``kept`` (the statements the builder cannot
 * show, which stay in the policy).
 */
export function builderStatements(
  publishers: BuilderPublisher[],
  choices: Choices,
  kept: PolicyStatement[] = [],
): PolicyStatement[] {
  const taken = new Set(kept.flatMap((s) => (s.sid ? [s.sid] : [])));
  const statements: PolicyStatement[] = [];
  for (const type of allTypes(publishers)) {
    const choice = choices[type.key];
    if (!choice || choice.actions.length === 0 || choice.resources.length === 0) continue;
    const actions = type.actions.map((a) => a.action).filter((a) => choice.actions.includes(a));
    if (actions.length === 0) continue;
    statements.push({ sid: uniqueSid(sidOf(actions), taken), effect: 'Allow', actions, resources: [...choice.resources] });
  }
  return statements;
}

/** The type a statement is a choice of: an Allow of actions the caller may grant of one type,
 *  on resources of that type; the type whose own step every resource names first. */
function typeOf(types: BuilderType[], statement: PolicyStatement): BuilderType | null {
  if (statement.effect !== 'Allow' || statement.actions.length === 0 || statement.resources.length === 0) return null;
  const fits = types.filter(
    (type) =>
      statement.actions.every((action) => type.actions.some((a) => a.action === action)) &&
      statement.resources.every((resource) => belongsTo(type, resource)),
  );
  return (
    fits.find((type) => statement.resources.every((r) => r.includes(type.marker))) ?? fits[0] ?? null
  );
}

/**
 * A document read back into choices: an Allow whose actions the caller may grant of one type,
 * on that type's resources, is that type's choice (the first such statement of a type); any
 * other statement (a Deny, actions of several types or that the caller may not grant, a
 * wildcard action, a second statement of a type) is kept as it is, in ``rest``.
 */
export function splitStatements(
  publishers: BuilderPublisher[],
  statements: PolicyStatement[],
): { choices: Choices; rest: PolicyStatement[] } {
  const types = allTypes(publishers);
  const choices: Choices = {};
  const rest: PolicyStatement[] = [];
  for (const statement of statements) {
    const type = typeOf(types, statement);
    if (type && !choices[type.key]) {
      choices[type.key] = { actions: [...statement.actions], resources: [...statement.resources] };
    } else {
      rest.push(statement);
    }
  }
  return { choices, rest };
}

// -- IAM's words ---------------------------------------------------------------------------

/** A pattern written at a scope (`${scope}` or `${scope}/...`) as it reads at ``scope``: a
 *  container's name, the platform `abi:` (where `${scope}/` reads `abi:`), or below a
 *  container (`<container>/*`), read at the container itself. */
export function atScope(pattern: string, scope: string): string {
  const container = scope.endsWith('/*') ? scope.slice(0, -2) : scope;
  if (pattern.startsWith(SCOPE_PREFIX)) {
    const rest = pattern.slice(SCOPE_PREFIX.length);
    return container === 'abi:' ? `abi:${rest}` : `${container}/${rest}`;
  }
  return pattern === SCOPE ? container : pattern;
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

const REFUSAL = /allows (\S+) on (\S+?)(?: at (\S+))?, and /;

/** The types whose choice an IAM refusal names ("You cannot grant what you do not hold: …
 *  allows <action> on <resource> at <scope>, and …"), the resource written `${scope}/` or placed. */
export function refusedTypes(publishers: BuilderPublisher[], choices: Choices, message: string, scope: string): string[] {
  const match = REFUSAL.exec(message);
  if (!match) return [];
  const [, action, resource, at] = match;
  const placedAt = at ?? scope;
  return allTypes(publishers)
    .filter((type) => {
      const choice = choices[type.key];
      return (
        !!choice &&
        choice.actions.includes(action) &&
        choice.resources.some((r) => r === resource || atScope(r, placedAt) === resource)
      );
    })
    .map((type) => type.key);
}
