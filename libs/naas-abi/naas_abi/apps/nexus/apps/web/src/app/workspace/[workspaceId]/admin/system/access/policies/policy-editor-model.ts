/**
 * The policy editor's logic, apart from the screen: the form state of a document, the
 * autocomplete of actions and resource names, wildcard counts and the text forms (JSON, YAML).
 *
 * Names follow IAM's grammar: actions `<service>:<Action>`, resources
 * `abi:<org>:<workspace>:<service>:<type>/<id>` (or `${scope}:<service>:<type>/<id>`), with the
 * wildcards `*` and `?` and the variables of `CatalogsView.variables`.
 */
import type {
  Catalog,
  CatalogsView,
  Effect,
  Level,
  PolicyDocument,
  PolicyStatement,
} from '@/lib/iam-admin/types';

export const POLICY_VERSION = '2026-10-13';

export type EditorStatement = {
  /** Stable across edits and moves, for React. */
  key: string;
  sid: string;
  effect: Effect;
  actions: string[];
  resources: string[];
};

let counter = 0;
function nextKey(): string {
  counter += 1;
  return `statement-${counter}`;
}

export function emptyStatement(): EditorStatement {
  return { key: nextKey(), sid: '', effect: 'Allow', actions: [], resources: [] };
}

export function fromDocument(document: PolicyDocument): EditorStatement[] {
  return document.statements.map((statement) => ({
    key: nextKey(),
    sid: statement.sid ?? '',
    effect: statement.effect,
    actions: [...statement.actions],
    resources: [...statement.resources],
  }));
}

export function toDocument(
  statements: EditorStatement[],
  version: string = POLICY_VERSION,
): PolicyDocument {
  return {
    version,
    statements: statements.map((statement): PolicyStatement => {
      const out: PolicyStatement = {
        effect: statement.effect,
        actions: [...statement.actions],
        resources: [...statement.resources],
      };
      const sid = statement.sid.trim();
      // `sid` first in the text forms, like IAM writes it.
      return sid ? { sid, ...out } : out;
    }),
  };
}

export function moveStatement(
  statements: EditorStatement[],
  index: number,
  by: -1 | 1,
): EditorStatement[] {
  const target = index + by;
  if (target < 0 || target >= statements.length) return statements;
  const next = [...statements];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_, i) => i !== index);
}

// -- patterns ---------------------------------------------------------------------------

export function hasWildcard(pattern: string): boolean {
  return pattern.includes('*') || pattern.includes('?');
}

/** Whether ``pattern`` (``*`` any run, ``?`` one character) matches ``value`` whole. */
export function matchPattern(pattern: string, value: string): boolean {
  let source = '^';
  for (const ch of pattern) {
    if (ch === '*') source += '.*';
    else if (ch === '?') source += '.';
    else source += ch.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp(`${source}$`, 's').test(value);
}

export type ActionEntry = {
  qualified: string;
  level: Level;
  description: string;
  service: string;
  resourceTypes: string[];
};

export function allActions(catalogs: Catalog[]): ActionEntry[] {
  return catalogs.flatMap((catalog) =>
    catalog.actions.map((action) => ({
      qualified: action.qualified,
      level: action.level,
      description: action.description,
      service: catalog.service,
      resourceTypes: action.resource_types,
    })),
  );
}

/** The catalog actions an action pattern names. */
export function matchingActions(pattern: string, catalogs: Catalog[]): ActionEntry[] {
  return allActions(catalogs).filter((entry) => matchPattern(pattern, entry.qualified));
}

// -- suggestions ------------------------------------------------------------------------

export type Suggestion = {
  /** What picking it puts in the field. */
  value: string;
  /** Shown beside the value: a level, a hint. */
  badge?: string;
  detail?: string;
  /** For a wildcard: how many catalog entries it matches. */
  count?: number;
};

const MAX_SUGGESTIONS = 8;

/** Actions for what was typed: wildcards say how many actions they name; otherwise the
 *  catalog's actions containing the text (those starting with it first), then ``service:*``. */
export function suggestActions(
  input: string,
  catalogs: Catalog[],
  limit: number = MAX_SUGGESTIONS,
): Suggestion[] {
  const text = input.trim();
  const actions = allActions(catalogs);
  const out: Suggestion[] = [];
  if (hasWildcard(text)) {
    const count = actions.filter((entry) => matchPattern(text, entry.qualified)).length;
    out.push({
      value: text,
      count,
      detail: count === 1 ? 'matches 1 action' : `matches ${count} actions`,
    });
  }
  const needle = text.replace(/[*?]/g, '').toLowerCase();
  const concrete = actions
    .filter((entry) => entry.qualified.toLowerCase().includes(needle))
    .sort((a, b) => {
      const aStart = a.qualified.toLowerCase().startsWith(needle) ? 0 : 1;
      const bStart = b.qualified.toLowerCase().startsWith(needle) ? 0 : 1;
      return aStart - bStart || a.qualified.localeCompare(b.qualified);
    });
  const services = catalogs
    .map((c) => c.service)
    .filter((service) => !hasWildcard(text) && `${service}:*`.startsWith(needle) && needle !== '')
    .map(
      (service): Suggestion => ({
        value: `${service}:*`,
        count: actions.filter((entry) => entry.service === service).length,
        detail: `every ${service} action`,
      }),
    );
  for (const suggestion of services) if (out.length < limit) out.push(suggestion);
  for (const entry of concrete) {
    if (out.length >= limit) break;
    if (out.some((s) => s.value === entry.qualified)) continue;
    out.push({ value: entry.qualified, badge: entry.level, detail: entry.description });
  }
  return out.slice(0, limit);
}

/** The resource types the chosen actions can act on, per service; ``null``: any type of it
 *  (no action chosen for the service, or a wildcard that reaches every type). */
export function typesOfActions(
  actions: string[],
  catalogs: Catalog[],
): Map<string, Set<string> | null> {
  const out = new Map<string, Set<string> | null>();
  if (actions.length === 0) return out;
  for (const pattern of actions) {
    const matched = matchingActions(pattern, catalogs);
    for (const entry of matched) {
      if (!out.has(entry.service)) out.set(entry.service, new Set());
      const types = out.get(entry.service);
      for (const type of entry.resourceTypes) types?.add(type);
    }
  }
  return out;
}

export type ResourceContext = {
  catalogs: CatalogsView | null;
  /** The statement's actions: they narrow the services and types suggested. */
  actions: string[];
};

function variableSuggestion(name: string): Suggestion {
  return name === 'scope'
    ? { value: '${scope}:', detail: 'the scope the policy is attached at' }
    : { value: `\${${name}}`, detail: 'a variable' };
}

/**
 * Resource names for what was typed, one segment at a time: the prefix (`abi:` or a
 * variable), the org and workspace (`*`, `-`), the service and type from the catalogs of the
 * chosen actions, then the id (`*`). Each suggestion is the whole text up to and including
 * its segment, so picking it continues the name.
 */
export function suggestResources(
  input: string,
  context: ResourceContext,
  limit: number = MAX_SUGGESTIONS,
): Suggestion[] {
  const text = input.trim();
  const catalogs = context.catalogs?.catalogs ?? [];
  const variables = context.catalogs?.variables ?? [];
  const chosen = typesOfActions(context.actions, catalogs);
  const services = catalogs.filter(
    (catalog) => chosen.size === 0 || chosen.has(catalog.service),
  );

  const typesOf = (catalog: Catalog): { name: string; id: string; detail: string }[] => {
    const wanted = chosen.get(catalog.service);
    return catalog.resource_types
      .filter((type) => !wanted || wanted.has(type.name))
      .map((type) => ({ name: type.name, id: type.id, detail: type.description }));
  };

  // First segment: `abi`, or a variable such as `${scope}`.
  if (!text.startsWith('abi:') && !text.startsWith('${scope}:')) {
    if (text.includes(':')) return [];
    const wants = text.toLowerCase();
    const candidates: Suggestion[] = [
      { value: 'abi:', detail: 'a resource name: abi:<org>:<workspace>:<service>:<type>/<id>' },
      ...variables.map(variableSuggestion),
      { value: '*', detail: 'every resource' },
    ];
    return candidates.filter((c) => c.value.toLowerCase().startsWith(wants)).slice(0, limit);
  }

  const lastColon = text.lastIndexOf(':');
  const head = text.slice(0, lastColon + 1);
  const typed = text.slice(lastColon + 1);
  const segments = head.split(':').slice(0, -1); // finished segments
  const scoped = segments[0] === '${scope}';
  const serviceIndex = scoped ? 1 : 3;

  const make = (value: string, detail?: string): Suggestion => ({ value: head + value, detail });
  const starts = (value: string) => value.toLowerCase().startsWith(typed.toLowerCase());

  if (!scoped && segments.length < 3) {
    // The org (index 1), then the workspace (index 2).
    const where = segments.length === 1 ? 'org' : 'workspace';
    return [
      make('*:', `every ${where}`),
      make('-:', where === 'org' ? 'the platform' : 'the organization itself'),
    ]
      .filter((s) => starts(s.value.slice(head.length)))
      .slice(0, limit);
  }

  if (segments.length === serviceIndex) {
    return services
      .filter((catalog) => starts(catalog.service))
      .map((catalog) => make(`${catalog.service}:`, `${catalog.resource_types.length} resource types`))
      .slice(0, limit);
  }

  if (segments.length === serviceIndex + 1) {
    const service = segments[serviceIndex];
    const catalog = catalogs.find((c) => c.service === service);
    if (!catalog) return [];
    const [typed_type, ...rest] = typed.split('/');
    if (rest.length === 0) {
      return typesOf(catalog)
        .filter((type) => starts(type.name))
        .map((type) => make(`${type.name}/`, type.detail || `a ${type.name}`))
        .slice(0, limit);
    }
    const type = catalog.resource_types.find((t) => t.name === typed_type);
    const base = `${head}${typed_type}/`;
    const idHint =
      type?.id === 'path'
        ? 'a path: <part>/<part>'
        : type?.id === 'singleton'
          ? 'the only one'
          : 'an id';
    const idTyped = rest.join('/');
    return '*'.startsWith(idTyped)
      ? [{ value: `${base}*`, detail: `every ${typed_type}: ${idHint}` }]
      : [];
  }
  return [];
}

// -- text forms ---------------------------------------------------------------------------

export type TextFormat = 'json' | 'yaml';

function yamlScalar(value: string): string {
  // Quote what YAML would read as something else: a plain scalar is safe only when it
  // starts with a letter, `*` is a YAML alias marker, `$` and `@` are reserved.
  return /^[A-Za-z][A-Za-z0-9_.\-]*$/.test(value) && !/^(true|false|null|yes|no|on|off)$/i.test(value)
    ? value
    : JSON.stringify(value);
}

/** A document as YAML (block style; strings JSON-quoted unless plain). */
export function toYaml(document: PolicyDocument): string {
  const lines = [`version: ${JSON.stringify(document.version)}`];
  if (document.statements.length === 0) {
    lines.push('statements: []');
  } else {
    lines.push('statements:');
    for (const statement of document.statements) {
      let first = true;
      const put = (text: string) => {
        lines.push(first ? `  - ${text}` : `    ${text}`);
        first = false;
      };
      if (statement.sid) put(`sid: ${yamlScalar(statement.sid)}`);
      put(`effect: ${statement.effect}`);
      for (const field of ['actions', 'resources'] as const) {
        if (statement[field].length === 0) {
          put(`${field}: []`);
        } else {
          put(`${field}:`);
          for (const value of statement[field]) lines.push(`      - ${JSON.stringify(value)}`);
        }
      }
    }
  }
  return `${lines.join('\n')}\n`;
}

export function toText(document: PolicyDocument, format: TextFormat): string {
  return format === 'yaml' ? toYaml(document) : `${JSON.stringify(document, null, 2)}\n`;
}

/** Which form a text is in, for the format switch: JSON starts with `{`. */
export function detectFormat(text: string): TextFormat {
  return text.trimStart().startsWith('{') ? 'json' : 'yaml';
}

/** Whether two documents say the same. */
export function sameDocument(a: PolicyDocument, b: PolicyDocument): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
