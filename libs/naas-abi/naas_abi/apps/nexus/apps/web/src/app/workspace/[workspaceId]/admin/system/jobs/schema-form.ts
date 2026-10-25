/**
 * Pure logic behind the workflow launch form: a JSON Schema as a list of form
 * fields, the values typed into them as a payload, and a validator for the
 * keywords a launch form needs. The API checks the input again with a full
 * validator: this one only has to catch what a person can fix before sending.
 *
 * The form covers strings, numbers, integers, booleans, enums, arrays of those
 * and nested objects (``$ref`` to the schema's own ``$defs``, and the
 * ``anyOf: [X, null]`` pydantic writes for optional fields, included). A schema
 * with anything else (unions, arrays of objects, free-form objects) has no form:
 * ``buildForm`` returns null and the dialog shows the raw JSON editor.
 */
import type { JsonSchema } from './jobs-types';

type Schema = Record<string, unknown>;

export interface Issue {
  /** A JSON pointer: ``/window/days``; empty for the whole input. */
  path: string;
  message: string;
}

export type Scalar = string | number | boolean;
export type FieldKind = 'string' | 'number' | 'integer' | 'boolean' | 'enum' | 'array' | 'object';

export interface FormField {
  name: string;
  label: string;
  description: string;
  required: boolean;
  kind: FieldKind;
  schema: Schema;
  /** Enum fields: the allowed values. */
  options: Scalar[];
  /** Array fields: how each item is entered. */
  item: FormField | null;
  /** Object fields: the nested fields. */
  fields: FormField[];
  default: unknown;
}

export type Values = Record<string, unknown>;

const isObject = (value: unknown): value is Schema =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

const isScalar = (value: unknown): value is Scalar =>
  typeof value === 'string' || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value));

export const pointer = (parent: string, key: string | number) =>
  `${parent}/${String(key).replace(/~/g, '~0').replace(/\//g, '~1')}`;

// --- references -----------------------------------------------------------------------

/** The schema a local ``$ref`` ("#/$defs/Name", "#/definitions/Name") points to, siblings kept. */
function deref(schema: Schema, root: Schema, seen: string[] = []): Schema | null {
  const ref = schema.$ref;
  if (typeof ref !== 'string') return schema;
  if (!ref.startsWith('#/') || seen.includes(ref)) return null;
  let target: unknown = root;
  for (const part of ref.slice(2).split('/')) {
    target = isObject(target) ? target[part.replace(/~1/g, '/').replace(/~0/g, '~')] : undefined;
  }
  if (!isObject(target)) return null;
  const { $ref: _ref, ...siblings } = schema;
  const resolved = deref(target, root, [...seen, ref]);
  return resolved ? { ...resolved, ...siblings } : null;
}

interface Normalized {
  schema: Schema;
  nullable: boolean;
}

/** ``schema`` with references and the optional-field wrappers resolved, or null if it is not one shape. */
function normalize(schema: unknown, root: Schema, depth = 0): Normalized | null {
  if (!isObject(schema) || depth > 12) return null;
  const resolved = deref(schema, root);
  if (!resolved) return null;
  let current = resolved;
  let nullable = false;

  if (Array.isArray(current.allOf) && current.allOf.length === 1) {
    const { allOf, ...outer } = current;
    const inner = normalize(allOf[0], root, depth + 1);
    if (!inner) return null;
    current = { ...inner.schema, ...outer };
    nullable = inner.nullable;
  }
  for (const key of ['anyOf', 'oneOf'] as const) {
    const branches = current[key];
    if (!Array.isArray(branches)) continue;
    const real = branches.filter((b) => !(isObject(b) && b.type === 'null'));
    if (real.length !== 1) return null;
    const { [key]: _union, ...outer } = current;
    const inner = normalize(real[0], root, depth + 1);
    if (!inner) return null;
    current = { ...inner.schema, ...outer };
    nullable = nullable || inner.nullable || real.length !== branches.length;
  }
  if (Array.isArray(current.type)) {
    const real = current.type.filter((t) => t !== 'null');
    if (real.length !== 1) return null;
    nullable = nullable || real.length !== current.type.length;
    current = { ...current, type: real[0] };
  }
  return { schema: current, nullable };
}

// --- the form ---------------------------------------------------------------------------

function scalarKind(schema: Schema): FieldKind | null {
  if (Array.isArray(schema.enum)) {
    return schema.enum.length && schema.enum.every(isScalar) ? 'enum' : null;
  }
  if (schema.type === 'string' || schema.type === 'number' || schema.type === 'integer' || schema.type === 'boolean') {
    return schema.type;
  }
  return null;
}

/** "dry_run" as "Dry run": the label of a field whose schema has no title. */
const humanize = (name: string) => {
  const words = name.replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

function field(name: string, raw: unknown, root: Schema, required: boolean, depth: number): FormField | null {
  const normalized = normalize(raw, root);
  if (!normalized) return null;
  const { schema } = normalized;
  const base = {
    name,
    label: typeof schema.title === 'string' && schema.title ? schema.title : humanize(name),
    description: typeof schema.description === 'string' ? schema.description : '',
    required,
    schema,
    options: [] as Scalar[],
    item: null as FormField | null,
    fields: [] as FormField[],
    default: schema.default,
  };
  const scalar = scalarKind(schema);
  if (scalar) return { ...base, kind: scalar, options: scalar === 'enum' ? (schema.enum as Scalar[]) : [] };
  if (schema.type === 'array') {
    const item = field(name, schema.items, root, true, depth + 1);
    if (!item || item.kind === 'array' || item.kind === 'object') return null;
    return { ...base, kind: 'array', item };
  }
  if (schema.type === 'object' || isObject(schema.properties)) {
    if (depth > 6) return null;
    const fields = objectFields(schema, root, depth + 1);
    return fields ? { ...base, kind: 'object', fields } : null;
  }
  return null;
}

function objectFields(schema: Schema, root: Schema, depth: number): FormField[] | null {
  // A free-form object (no declared properties) has nothing to render.
  if (!isObject(schema.properties) || !Object.keys(schema.properties).length) return null;
  const required = Array.isArray(schema.required) ? schema.required : [];
  const fields: FormField[] = [];
  for (const [name, raw] of Object.entries(schema.properties)) {
    const built = field(name, raw, root, required.includes(name), depth);
    if (!built) return null;
    fields.push(built);
  }
  return fields;
}

/** The form for an input schema, or null when the schema needs the raw JSON editor. */
export function buildForm(schema: JsonSchema | null | undefined): FormField[] | null {
  if (!schema || !isObject(schema)) return null;
  const normalized = normalize(schema, schema);
  if (!normalized || normalized.schema.type !== 'object') return null;
  return objectFields(normalized.schema, schema, 0);
}

// --- values -----------------------------------------------------------------------------

/** The form's starting values: the schema's defaults under what ``payload`` already has. */
export function initialValues(fields: FormField[], payload: unknown): Values {
  const given = isObject(payload) ? structuredClone(payload) : {};
  return withDefaults(fields, given);
}

function withDefaults(fields: FormField[], values: Values): Values {
  for (const f of fields) {
    if (values[f.name] !== undefined) {
      if (f.kind === 'object' && isObject(values[f.name])) values[f.name] = withDefaults(f.fields, values[f.name] as Values);
      continue;
    }
    if (f.default !== undefined) values[f.name] = structuredClone(f.default);
    else if (f.kind === 'object' && f.required) values[f.name] = withDefaults(f.fields, {});
  }
  return values;
}

export type Path = (string | number)[];

export function getIn(values: unknown, path: Path): unknown {
  let current = values;
  for (const key of path) {
    if (current === null || typeof current !== 'object') return undefined;
    current = (current as Record<string | number, unknown>)[key];
  }
  return current;
}

/** ``values`` with ``value`` at ``path`` (undefined removes it); nothing is changed in place. */
export function setIn(values: Values, path: Path, value: unknown): Values {
  const [head, ...rest] = path;
  const copy: Values | unknown[] = Array.isArray(values) ? [...values] : { ...values };
  const target = copy as Record<string | number, unknown>;
  if (rest.length) {
    const child = target[head];
    target[head] = setIn((child !== null && typeof child === 'object' ? child : typeof rest[0] === 'number' ? [] : {}) as Values, rest, value);
  } else if (value === undefined) {
    if (Array.isArray(copy)) copy.splice(Number(head), 1);
    else delete target[head];
  } else {
    target[head] = value;
  }
  return copy as Values;
}

function empty(value: unknown): boolean {
  return value === undefined || (Array.isArray(value) && value.length === 0) || (isObject(value) && Object.keys(value).length === 0);
}

/** The payload to send: ``values`` without optional objects and lists left empty. */
export function toPayload(fields: FormField[], values: Values): Values {
  const out: Values = { ...values };
  for (const f of fields) {
    const value = out[f.name];
    if (f.kind === 'object' && isObject(value)) out[f.name] = toPayload(f.fields, value);
    if (!f.required && empty(out[f.name]) && f.default === undefined) delete out[f.name];
  }
  return out;
}

/** The values typed into the form, and the text of number fields (``drafts``, by pointer)
 * so that "1." or "-" can be typed on the way to a number. */
export interface FormState {
  values: Values;
  drafts: Record<string, string>;
}

export const pathPointer = (path: Path) => path.reduce<string>((p, key) => pointer(p, key), '');

export function edit(state: FormState, path: Path, value: unknown): FormState {
  return { values: setIn(state.values, path, value), drafts: state.drafts };
}

/** A number field typed into: its text is kept, and its value is the number it reads as. */
export function editNumber(state: FormState, path: Path, text: string, integer: boolean): FormState {
  const read = parseNumber(text, integer);
  const value = 'value' in read ? read.value : undefined;
  // A list item that is not a number yet stays in the list (blank), it is not removed.
  const blank = typeof path[path.length - 1] === 'number' ? null : undefined;
  return {
    values: setIn(state.values, path, value ?? blank),
    drafts: { ...state.drafts, [pathPointer(path)]: text },
  };
}

/** Forget typed text under ``path`` (a list's items moved). */
export function clearDrafts(state: FormState, path: Path): FormState {
  const prefix = pathPointer(path) + '/';
  return {
    values: state.values,
    drafts: Object.fromEntries(Object.entries(state.drafts).filter(([key]) => !key.startsWith(prefix))),
  };
}

/** Number fields whose text is not a number: only the form knows these (their value is blank). */
export function draftIssues(fields: FormField[], state: FormState): Issue[] {
  const issues: Issue[] = [];
  const visit = (list: FormField[], parent: Path) => {
    for (const f of list) {
      const path = [...parent, f.name];
      if (f.kind === 'object') visit(f.fields, path);
      const leaves: [FormField, Path][] =
        f.kind === 'array' && f.item
          ? (getIn(state.values, path) as unknown[] | undefined ?? []).map((_, i) => [f.item as FormField, [...path, i]] as [FormField, Path])
          : [[f, path]];
      for (const [leaf, at] of leaves) {
        if (leaf.kind !== 'number' && leaf.kind !== 'integer') continue;
        const text = state.drafts[pathPointer(at)];
        const read = text === undefined ? null : parseNumber(text, leaf.kind === 'integer');
        if (read && 'error' in read) issues.push({ path: pathPointer(at), message: read.error });
      }
    }
  };
  visit(fields, []);
  return issues;
}

/** Everything wrong with the form, ``issues`` first by the number fields' own messages. */
export function formIssues(schema: JsonSchema, fields: FormField[], state: FormState): Issue[] {
  const drafts = draftIssues(fields, state);
  const blank = new Set(drafts.map((d) => d.path));
  const found = validate(schema, toPayload(fields, state.values)).filter((i) => !blank.has(i.path));
  return [...drafts, ...found];
}

/** What a typed number is: its value (undefined when blank), or why it is not one. */
export function parseNumber(text: string, integer: boolean): { value: number | undefined } | { error: string } {
  const trimmed = text.trim();
  if (!trimmed) return { value: undefined };
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return { error: 'Enter a number.' };
  if (integer && !Number.isInteger(value)) return { error: 'Enter a whole number.' };
  return { value };
}

// --- validation -------------------------------------------------------------------------

const MAX_ISSUES = 20;

function matchesType(type: unknown, value: unknown): boolean {
  switch (type) {
    case 'string':
      return typeof value === 'string';
    case 'number':
      return typeof value === 'number' && Number.isFinite(value);
    case 'integer':
      return typeof value === 'number' && Number.isInteger(value);
    case 'boolean':
      return typeof value === 'boolean';
    case 'null':
      return value === null;
    case 'object':
      return isObject(value);
    case 'array':
      return Array.isArray(value);
    default:
      return true;
  }
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

function check(schema: unknown, value: unknown, path: string, root: Schema, issues: Issue[], depth: number): void {
  if (!isObject(schema) || depth > 20 || issues.length >= MAX_ISSUES) return;
  const s = deref(schema, root);
  if (!s) return;
  const add = (message: string, at = path): void => {
    issues.push({ path: at, message });
  };

  if (Array.isArray(s.allOf)) s.allOf.forEach((sub) => check(sub, value, path, root, issues, depth + 1));
  for (const key of ['anyOf', 'oneOf'] as const) {
    const branches = s[key];
    if (!Array.isArray(branches)) continue;
    const fits = branches.some((sub) => {
      const found: Issue[] = [];
      check(sub, value, path, root, found, depth + 1);
      return found.length === 0;
    });
    if (!fits) add('Does not match any of the allowed shapes.');
  }

  const types = Array.isArray(s.type) ? s.type : s.type ? [s.type] : [];
  if (types.length && !types.some((t) => matchesType(t, value))) {
    return add(`Must be ${types.map((t) => (t === 'integer' ? 'a whole number' : `a ${t}`)).join(' or ')}.`);
  }
  if (Array.isArray(s.enum) && !s.enum.some((option) => same(option, value))) {
    return add(`Must be one of: ${s.enum.map((o) => JSON.stringify(o)).join(', ')}.`);
  }
  if ('const' in s && !same(s.const, value)) return add(`Must be ${JSON.stringify(s.const)}.`);

  if (typeof value === 'string') {
    if (typeof s.minLength === 'number' && value.length < s.minLength) add(`At least ${s.minLength} characters.`);
    if (typeof s.maxLength === 'number' && value.length > s.maxLength) add(`At most ${s.maxLength} characters.`);
    if (typeof s.pattern === 'string') {
      try {
        if (!new RegExp(s.pattern, 'u').test(value)) add(`Must match ${s.pattern}.`);
      } catch {
        // A pattern this engine cannot read is the API's to check.
      }
    }
  }
  if (typeof value === 'number') {
    if (typeof s.minimum === 'number' && value < s.minimum) add(`At least ${s.minimum}.`);
    if (typeof s.maximum === 'number' && value > s.maximum) add(`At most ${s.maximum}.`);
    if (typeof s.exclusiveMinimum === 'number' && value <= s.exclusiveMinimum) add(`Greater than ${s.exclusiveMinimum}.`);
    if (typeof s.exclusiveMaximum === 'number' && value >= s.exclusiveMaximum) add(`Less than ${s.exclusiveMaximum}.`);
  }
  if (Array.isArray(value)) {
    if (typeof s.minItems === 'number' && value.length < s.minItems) add(`At least ${s.minItems} items.`);
    if (typeof s.maxItems === 'number' && value.length > s.maxItems) add(`At most ${s.maxItems} items.`);
    if (isObject(s.items)) value.forEach((item, i) => check(s.items, item, pointer(path, i), root, issues, depth + 1));
  }
  if (isObject(value)) {
    const properties = isObject(s.properties) ? s.properties : {};
    for (const name of Array.isArray(s.required) ? s.required : []) {
      if (typeof name === 'string' && value[name] === undefined) add('Required.', pointer(path, name));
    }
    for (const [name, sub] of Object.entries(properties)) {
      if (value[name] !== undefined) check(sub, value[name], pointer(path, name), root, issues, depth + 1);
    }
    if (s.additionalProperties === false) {
      for (const name of Object.keys(value)) if (!(name in properties)) add('Not an input of this workflow.', pointer(path, name));
    }
  }
}

/** Why ``value`` does not match ``schema`` (at most 20 faults; empty: it does). */
export function validate(schema: JsonSchema, value: unknown): Issue[] {
  const issues: Issue[] = [];
  check(schema, value, '', schema, issues, 0);
  return issues.slice(0, MAX_ISSUES);
}
