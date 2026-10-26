import { describe, expect, it } from 'vitest';
import { INGEST_SCHEMA } from './jobs-fixtures';
import {
  buildForm,
  clearDrafts,
  draftIssues,
  edit,
  editNumber,
  formIssues,
  getIn,
  initialValues,
  parseNumber,
  pathPointer,
  setIn,
  toPayload,
  validate,
} from './schema-form';

const names = (fields: ReturnType<typeof buildForm>) => fields?.map((f) => `${f.name}:${f.kind}${f.required ? '!' : ''}`);

describe('buildForm', () => {
  it('renders strings, numbers, integers, booleans, enums, lists of scalars and nested objects', () => {
    const form = buildForm(INGEST_SCHEMA);

    expect(names(form)).toEqual([
      'filter:string!',
      'limit:integer',
      'ratio:number',
      'dry_run:boolean',
      'mode:enum',
      'tags:array',
      'window:object',
    ]);
    expect(form?.[0]).toMatchObject({ label: 'Filter', description: 'Keyword to search for' });
    // Without a title, the name is the label.
    expect(form?.map((f) => f.label)).toEqual(['Filter', 'Limit', 'Ratio', 'Dry run', 'Mode', 'Tags', 'Window']);
    expect(form?.[4].options).toEqual(['fast', 'full']);
    expect(form?.[5].item?.kind).toBe('string');
    expect(names(form?.[6].fields ?? null)).toEqual(['days:integer', 'label:string']);
  });

  it('follows local references and the optional wrappers pydantic writes', () => {
    const schema = {
      type: 'object',
      $defs: { Window: { type: 'object', properties: { days: { type: 'integer' } }, required: ['days'] } },
      properties: {
        window: { $ref: '#/$defs/Window' },
        maybe_window: { anyOf: [{ $ref: '#/$defs/Window' }, { type: 'null' }], title: 'Maybe' },
        note: { anyOf: [{ type: 'string' }, { type: 'null' }], default: null },
        kind: { allOf: [{ enum: ['a', 'b'] }], description: 'Which' },
        count: { type: ['integer', 'null'] },
      },
      required: ['window'],
    };

    const form = buildForm(schema);

    expect(names(form)).toEqual(['window:object!', 'maybe_window:object', 'note:string', 'kind:enum', 'count:integer']);
    expect(form?.[0].fields[0]).toMatchObject({ name: 'days', required: true });
    expect(form?.[1].label).toBe('Maybe');
    expect(form?.[3].description).toBe('Which');
  });

  it('lists the required fields first, each group in the schema order', () => {
    const schema = {
      type: 'object',
      properties: { a: { type: 'string' }, b: { type: 'string' }, c: { type: 'string' }, d: { type: 'string' } },
      required: ['d', 'b'],
    };

    expect(buildForm(schema)?.map((f) => f.name)).toEqual(['b', 'd', 'a', 'c']);
  });

  it.each([
    ['no schema', null],
    ['a root that is not an object', { type: 'array', items: { type: 'string' } }],
    ['an object without declared properties', { type: 'object' }],
    ['a free-form object field', { type: 'object', properties: { extra: { type: 'object', additionalProperties: true } } }],
    ['a union', { type: 'object', properties: { v: { anyOf: [{ type: 'string' }, { type: 'integer' }] } } }],
    ['a list of objects', { type: 'object', properties: { v: { type: 'array', items: { type: 'object', properties: { a: { type: 'string' } } } } } }],
    ['a list of lists', { type: 'object', properties: { v: { type: 'array', items: { type: 'array', items: { type: 'string' } } } } }],
    ['a reference it cannot resolve', { type: 'object', properties: { v: { $ref: '#/$defs/Missing' } } }],
    ['a reference to elsewhere', { type: 'object', properties: { v: { $ref: 'https://example.com/s.json' } } }],
    ['a reference to itself', { type: 'object', $defs: { A: { $ref: '#/$defs/A' } }, properties: { v: { $ref: '#/$defs/A' } } }],
    ['an enum of objects', { type: 'object', properties: { v: { enum: [{ a: 1 }] } } }],
    ['a field with no type', { type: 'object', properties: { v: {} } }],
  ])('has no form for %s', (_, schema) => {
    expect(buildForm(schema as Record<string, unknown> | null)).toBeNull();
  });
});

describe('values', () => {
  const form = buildForm(INGEST_SCHEMA)!;

  it('starts from the schema defaults, under an earlier payload', () => {
    expect(initialValues(form, {})).toEqual({ limit: 10, dry_run: false, mode: 'fast' });
    expect(initialValues(form, { filter: 'news', limit: 3, extra: 1 })).toEqual({
      filter: 'news',
      limit: 3,
      dry_run: false,
      mode: 'fast',
      extra: 1, // kept: a form must not lose what it cannot show
    });
  });

  it('sets and removes values without changing the originals', () => {
    const values = { a: { b: 1 }, tags: ['x', 'y'] };

    expect(setIn(values, ['a', 'b'], 2)).toEqual({ a: { b: 2 }, tags: ['x', 'y'] });
    expect(setIn(values, ['a', 'c'], 3)).toEqual({ a: { b: 1, c: 3 }, tags: ['x', 'y'] });
    expect(setIn(values, ['a', 'b'], undefined)).toEqual({ a: {}, tags: ['x', 'y'] });
    expect(setIn(values, ['tags', 1], 'z')).toEqual({ a: { b: 1 }, tags: ['x', 'z'] });
    expect(setIn(values, ['tags', 0], undefined)).toEqual({ a: { b: 1 }, tags: ['y'] });
    expect(setIn({}, ['w', 'days'], 4)).toEqual({ w: { days: 4 } });
    expect(setIn({}, ['tags', 0], 'a')).toEqual({ tags: ['a'] });
    expect(values).toEqual({ a: { b: 1 }, tags: ['x', 'y'] });
    expect(getIn(values, ['a', 'b'])).toBe(1);
    expect(getIn(values, ['a', 'zz', 'b'])).toBeUndefined();
  });

  it('leaves optional objects and lists out when they are empty', () => {
    expect(toPayload(form, { filter: 'news', tags: [], window: {}, mode: 'fast' })).toEqual({ filter: 'news', mode: 'fast' });
    expect(toPayload(form, { filter: 'news', tags: ['a'], window: { days: 2 } })).toEqual({
      filter: 'news',
      tags: ['a'],
      window: { days: 2 },
    });
  });

  it('reads typed numbers', () => {
    expect(parseNumber(' 4 ', true)).toEqual({ value: 4 });
    expect(parseNumber('', true)).toEqual({ value: undefined });
    expect(parseNumber('2.5', false)).toEqual({ value: 2.5 });
    expect(parseNumber('2.5', true)).toEqual({ error: 'Enter a whole number.' });
    expect(parseNumber('abc', false)).toEqual({ error: 'Enter a number.' });
    expect(parseNumber('Infinity', false)).toEqual({ error: 'Enter a number.' });
  });
});

describe('validate', () => {
  it('accepts what matches', () => {
    expect(validate(INGEST_SCHEMA, { filter: 'news', limit: 3, tags: ['a'], window: { days: 1 }, mode: 'full' })).toEqual([]);
  });

  it('names each fault at its pointer', () => {
    const issues = validate(INGEST_SCHEMA, { limit: 0, dry_run: 'yes', mode: 'slow', tags: ['a', 2], window: { days: 1.5 } });

    expect(issues).toEqual([
      { path: '/filter', message: 'Required.' },
      { path: '/limit', message: 'At least 1.' },
      { path: '/dry_run', message: 'Must be a boolean.' },
      { path: '/mode', message: 'Must be one of: "fast", "full".' },
      { path: '/tags/1', message: 'Must be a string.' },
      { path: '/window/days', message: 'Must be a whole number.' },
    ]);
  });

  it('checks lengths, patterns, bounds and counts', () => {
    const schema = {
      type: 'object',
      properties: {
        s: { type: 'string', minLength: 2, maxLength: 3, pattern: '^[a-z]+$' },
        n: { type: 'number', exclusiveMinimum: 0, maximum: 10 },
        l: { type: 'array', items: { type: 'integer' }, minItems: 1, maxItems: 2 },
      },
      additionalProperties: false,
    };

    expect(validate(schema, { s: 'A', n: 0, l: [] }).map((i) => i.path + ' ' + i.message)).toEqual([
      '/s At least 2 characters.',
      '/s Must match ^[a-z]+$.',
      '/n Greater than 0.',
      '/l At least 1 items.',
    ]);
    expect(validate(schema, { s: 'abcd', n: 11, l: [1, 2, 3], other: 1 }).map((i) => i.path)).toEqual(['/s', '/n', '/l', '/other']);
  });

  it('follows references, optional wrappers and unions', () => {
    const schema = {
      type: 'object',
      $defs: { W: { type: 'object', properties: { days: { type: 'integer' } }, required: ['days'] } },
      properties: {
        w: { anyOf: [{ $ref: '#/$defs/W' }, { type: 'null' }] },
        u: { anyOf: [{ type: 'string' }, { type: 'integer' }] },
      },
    };

    expect(validate(schema, { w: null, u: 3 })).toEqual([]);
    expect(validate(schema, { w: {}, u: 'x' })).toEqual([{ path: '/w', message: 'Does not match any of the allowed shapes.' }]);
    expect(validate(schema, { u: [] })).toEqual([{ path: '/u', message: 'Does not match any of the allowed shapes.' }]);
  });

  it('ignores keywords it does not know and patterns it cannot read', () => {
    expect(validate({ type: 'object', properties: { s: { type: 'string', pattern: '(' } }, format: 'whatever' }, { s: 'x' })).toEqual([]);
    expect(validate({ type: 'object', properties: { s: { $ref: '#/$defs/none' } } }, { s: 1 })).toEqual([]);
  });

  it('stops at twenty faults', () => {
    expect(validate({ type: 'array', items: { type: 'integer' } }, Array(100).fill('x'))).toHaveLength(20);
  });
});

describe('form state', () => {
  const form = buildForm(INGEST_SCHEMA)!;
  const fresh = () => ({ values: initialValues(form, {}), drafts: {} });

  it('keeps what is typed into a number field while it reads as a number or not', () => {
    let state = editNumber(fresh(), ['ratio'], '1.', false);
    expect(state.values.ratio).toBe(1);
    expect(state.drafts).toEqual({ '/ratio': '1.' });

    state = editNumber(state, ['ratio'], '-', false);
    expect(state.values.ratio).toBeUndefined();
    expect(draftIssues(form, state)).toEqual([{ path: '/ratio', message: 'Enter a number.' }]);

    state = editNumber(state, ['window', 'days'], '2.5', true);
    expect(draftIssues(form, state).map((i) => i.path)).toEqual(['/ratio', '/window/days']);
  });

  it('reports a number field that cannot be read once, not also as missing', () => {
    const schema = { type: 'object', properties: { n: { type: 'integer' } }, required: ['n'] };
    const fields = buildForm(schema)!;
    const state = editNumber({ values: {}, drafts: {} }, ['n'], 'x', true);

    expect(formIssues(schema, fields, state)).toEqual([{ path: '/n', message: 'Enter a number.' }]);
    expect(formIssues(schema, fields, { values: {}, drafts: {} })).toEqual([{ path: '/n', message: 'Required.' }]);
  });

  it('checks number fields in lists by position and forgets their text when the list changes', () => {
    const schema = { type: 'object', properties: { ids: { type: 'array', items: { type: 'integer' } } } };
    const fields = buildForm(schema)!;
    let state = edit({ values: {}, drafts: {} }, ['ids'], [1, 2]);
    state = editNumber(state, ['ids', 1], '2x', true);

    expect(draftIssues(fields, state)).toEqual([{ path: '/ids/1', message: 'Enter a number.' }]);
    expect(clearDrafts(state, ['ids']).drafts).toEqual({});
    expect(pathPointer(['a/b', 0])).toBe('/a~1b/0');
  });

  it('puts the form in the payload the API validates', () => {
    let state = editNumber(fresh(), ['limit'], '0', true);
    state = edit(state, ['tags'], ['a']);

    expect(formIssues(INGEST_SCHEMA, form, state)).toEqual([
      { path: '/filter', message: 'Required.' },
      { path: '/limit', message: 'At least 1.' },
    ]);
    expect(toPayload(form, edit(state, ['filter'], 'news').values)).toEqual({
      filter: 'news',
      limit: 0,
      dry_run: false,
      mode: 'fast',
      tags: ['a'],
    });
  });
});
