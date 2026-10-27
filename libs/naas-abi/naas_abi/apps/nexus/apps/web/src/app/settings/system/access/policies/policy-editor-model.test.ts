import { describe, expect, it } from 'vitest';
import { catalogsView } from '../access-fixtures';
import {
  emptyStatement,
  fromDocument,
  matchPattern,
  matchingActions,
  moveStatement,
  sameDocument,
  suggestActions,
  suggestResources,
  toDocument,
  toText,
  toYaml,
  typesOfActions,
} from './policy-editor-model';

const catalogs = catalogsView.catalogs;

describe('wildcards', () => {
  it('matches * and ? against whole names', () => {
    expect(matchPattern('triple_store:*', 'triple_store:Query')).toBe(true);
    expect(matchPattern('triple_store:Quer?', 'triple_store:Query')).toBe(true);
    expect(matchPattern('triple_store:Quer', 'triple_store:Query')).toBe(false);
    expect(matchPattern('a.b', 'axb')).toBe(false);
  });

  it('counts the catalog actions a pattern names', () => {
    expect(matchingActions('triple_store:*', catalogs)).toHaveLength(4);
    expect(matchingActions('*', catalogs)).toHaveLength(6);
    expect(matchingActions('triple_store:List*', catalogs).map((a) => a.qualified)).toEqual([
      'triple_store:ListGraphs',
    ]);
  });
});

describe('action suggestions', () => {
  it('completes from the catalogs, starting with what starts with the text', () => {
    const found = suggestActions('triple_store:Q', catalogs);
    expect(found[0]).toMatchObject({ value: 'triple_store:Query', badge: 'read' });
    expect(found[0].detail).toBe('Run a SPARQL query.');
  });

  it('finds an action by a part of its name', () => {
    expect(suggestActions('graph', catalogs).map((s) => s.value)).toEqual([
      'triple_store:DropGraph',
      'triple_store:ListGraphs',
    ]);
  });

  it('says how many actions a wildcard names, and offers the service wildcard', () => {
    const found = suggestActions('triple_store:*', catalogs);
    expect(found[0]).toMatchObject({ value: 'triple_store:*', count: 4, detail: 'matches 4 actions' });
    expect(suggestActions('trip', catalogs).map((s) => s.value)).toContain('triple_store:*');
  });
});

describe('resource suggestions', () => {
  const context = (actions: string[]) => ({ catalogs: catalogsView, actions });

  it('starts with the prefix and the variables', () => {
    expect(suggestResources('', context([])).map((s) => s.value)).toEqual([
      'abi:',
      '${scope}:',
      '${principal.id}',
      '${user.id}',
      '*',
    ]);
    expect(suggestResources('${s', context([])).map((s) => s.value)).toEqual(['${scope}:']);
  });

  it('walks the name: org, workspace, service, type, id', () => {
    expect(suggestResources('abi:', context([])).map((s) => s.value)).toEqual(['abi:*:', 'abi:-:']);
    expect(suggestResources('abi:acme:', context([])).map((s) => s.value)).toEqual([
      'abi:acme:*:',
      'abi:acme:-:',
    ]);
    expect(suggestResources('abi:acme:ws-1:', context([])).map((s) => s.value)).toEqual([
      'abi:acme:ws-1:triple_store:',
      'abi:acme:ws-1:iam:',
    ]);
    expect(suggestResources('abi:acme:ws-1:triple_store:', context([])).map((s) => s.value)).toEqual([
      'abi:acme:ws-1:triple_store:graph/',
    ]);
    expect(
      suggestResources('abi:acme:ws-1:triple_store:graph/', context([])).map((s) => s.value),
    ).toEqual(['abi:acme:ws-1:triple_store:graph/*']);
  });

  it('keeps to the services and types of the chosen actions', () => {
    expect(
      suggestResources('abi:acme:ws-1:', context(['triple_store:Query'])).map((s) => s.value),
    ).toEqual(['abi:acme:ws-1:triple_store:']);
    expect(
      suggestResources('abi:-:-:iam:', context(['iam:ListKeys'])).map((s) => s.value),
    ).toEqual(['abi:-:-:iam:key/']);
  });

  it('follows ${scope}: the service comes right after it', () => {
    expect(suggestResources('${scope}:', context([])).map((s) => s.value)).toEqual([
      '${scope}:triple_store:',
      '${scope}:iam:',
    ]);
    expect(suggestResources('${scope}:triple_store:g', context([])).map((s) => s.value)).toEqual([
      '${scope}:triple_store:graph/',
    ]);
  });

  it('knows which types the actions reach', () => {
    const types = typesOfActions(['iam:*', 'triple_store:Query'], catalogs);
    expect([...(types.get('iam') ?? [])].sort()).toEqual(['key', 'policy']);
    expect([...(types.get('triple_store') ?? [])]).toEqual(['graph']);
  });
});

describe('document and form', () => {
  const document = {
    version: '2026-10-13',
    statements: [
      { sid: 'Read', effect: 'Allow' as const, actions: ['triple_store:Query'], resources: ['abi:a:b:c:d/e'] },
      { effect: 'Deny' as const, actions: ['triple_store:DropGraph'], resources: ['*'] },
    ],
  };

  it('round-trips through the form state', () => {
    expect(toDocument(fromDocument(document), document.version)).toEqual(document);
  });

  it('leaves out an empty sid and moves statements', () => {
    const state = fromDocument(document);
    const moved = moveStatement(state, 1, -1);
    expect(moved.map((s) => s.effect)).toEqual(['Deny', 'Allow']);
    expect(moveStatement(state, 0, -1)).toBe(state);
    expect('sid' in toDocument([emptyStatement()]).statements[0]).toBe(false);
  });

  it('writes YAML and JSON', () => {
    expect(toYaml(document)).toBe(
      [
        'version: "2026-10-13"',
        'statements:',
        '  - sid: Read',
        '    effect: Allow',
        '    actions:',
        '      - "triple_store:Query"',
        '    resources:',
        '      - "abi:a:b:c:d/e"',
        '  - effect: Deny',
        '    actions:',
        '      - "triple_store:DropGraph"',
        '    resources:',
        '      - "*"',
        '',
      ].join('\n'),
    );
    expect(JSON.parse(toText(document, 'json'))).toEqual(document);
    expect(sameDocument(document, JSON.parse(toText(document, 'json')))).toBe(true);
  });
});

describe('module scope ids', () => {
  const moduleCatalog = {
    service: 'module',
    version: 1,
    actions: [{ name: 'UseAgent', level: 'write', resource_types: ['agent'], description: '' }],
    resource_types: [{ name: 'agent', id: 'path', description: 'An agent of a module.' }],
  };
  const withModules = {
    catalogs: { ...catalogsView, catalogs: [...catalogsView.catalogs, moduleCatalog] },
    actions: ['module:UseAgent'],
    modules: {
      modules: [
        {
          module: 'acme.people',
          agents: [
            {
              name: 'Recruiter',
              display_name: 'Recruiter',
              description: 'Finds people.',
              icon: null,
              resource: '${scope}:module:agent/acme.people/Recruiter',
              actions: ['module:UseAgent'],
            },
          ],
          apps: [],
          workflows: [],
          pipelines: [],
          declared: null,
        },
      ],
    },
  } as Parameters<typeof suggestResources>[1];

  it('suggests each module and each of its agents from the listing', () => {
    expect(suggestResources('${scope}:module:agent/', withModules).map((s) => s.value)).toEqual([
      '${scope}:module:agent/*',
      '${scope}:module:agent/acme.people/*',
      '${scope}:module:agent/acme.people/Recruiter',
    ]);
    const typed = suggestResources('${scope}:module:agent/acme.people/R', withModules);
    expect(typed).toEqual([
      { value: '${scope}:module:agent/acme.people/Recruiter', detail: 'Recruiter: Finds people.' },
    ]);
  });

  it('suggests only `*` without the listing', () => {
    const context = { ...withModules, modules: null };
    expect(suggestResources('${scope}:module:agent/', context).map((s) => s.value)).toEqual([
      '${scope}:module:agent/*',
    ]);
  });
});
