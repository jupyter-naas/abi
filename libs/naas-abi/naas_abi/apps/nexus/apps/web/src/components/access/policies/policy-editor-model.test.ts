import { describe, expect, it } from 'vitest';
import type { Publisher } from '@/lib/iam-admin/types';
import { WS, catalogsView, publishedType } from '../access-fixtures';
import {
  emptyStatement,
  fromDocument,
  grantableCatalogs,
  grantablePatterns,
  matchPattern,
  matchingActions,
  moveStatement,
  sameDocument,
  suggestActions,
  suggestResources,
  toDocument,
  toText,
  toYaml,
  typedStep,
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
    expect(matchingActions('*', catalogs)).toHaveLength(7);
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
  const context = (actions: string[]) => ({ catalogs, variables: catalogsView.variables, actions });

  it('starts with the prefix and the variables', () => {
    expect(suggestResources('', context([])).map((s) => s.value)).toEqual([
      'abi:',
      '${scope}/',
      '${scope}',
      '${principal.id}',
      '${user.id}',
    ]);
    expect(suggestResources('${s', context([])).map((s) => s.value)).toEqual(['${scope}/', '${scope}']);
  });

  it('walks the name: containers, service, type, id', () => {
    expect(suggestResources('abi:', context([])).map((s) => s.value)).toEqual([
      'abi:*/',
      'abi:triple_store:',
      'abi:iam:',
      'abi:nexus:',
    ]);
    expect(suggestResources('abi:nexus:', context([])).map((s) => s.value)).toEqual([
      'abi:nexus:organization/',
      'abi:nexus:workspace/',
    ]);
    expect(suggestResources('abi:nexus:organization/', context([]))).toEqual([
      { value: 'abi:nexus:organization/*', detail: 'every organization: a container: what it holds comes after it' },
    ]);
    expect(suggestResources('abi:nexus:organization/acme/', context([])).map((s) => s.value)).toEqual([
      'abi:nexus:organization/acme/*',
      'abi:nexus:organization/acme/triple_store:',
      'abi:nexus:organization/acme/iam:',
      'abi:nexus:organization/acme/nexus:',
    ]);
    const ws = 'abi:nexus:organization/acme/nexus:workspace/ws-1/';
    expect(suggestResources(`${ws}triple_store:`, context([])).map((s) => s.value)).toEqual([
      `${ws}triple_store:graph/`,
    ]);
    expect(suggestResources(`${ws}triple_store:graph/`, context([])).map((s) => s.value)).toEqual([
      `${ws}triple_store:graph/*`,
    ]);
  });

  it('offers `*` + `/` after `abi:`, any container, and nothing inside a resource', () => {
    expect(suggestResources('abi:*/tr', context([])).map((s) => s.value)).toEqual(['abi:*/triple_store:']);
    expect(suggestResources('abi:triple_store:graph/main/', context([])).map((s) => s.value)).toEqual([]);
    expect(suggestResources('abi:acme/', context([])).map((s) => s.value)).toEqual([]);
    expect(suggestResources('abi:nexus:organization/a/b/', context([])).map((s) => s.value)).toEqual([]);
  });

  it('keeps to the services and types of the chosen actions, and the containers', () => {
    expect(
      suggestResources('abi:nexus:organization/acme/', context(['triple_store:Query'])).map((s) => s.value),
    ).toEqual([
      'abi:nexus:organization/acme/*',
      'abi:nexus:organization/acme/triple_store:',
      'abi:nexus:organization/acme/nexus:',
    ]);
    expect(suggestResources('abi:iam:', context(['iam:ListKeys'])).map((s) => s.value)).toEqual(['abi:iam:key/']);
  });

  it('follows ${scope}/: a step comes right after it', () => {
    expect(suggestResources('${scope}/', context([])).map((s) => s.value)).toEqual([
      '${scope}/triple_store:',
      '${scope}/iam:',
      '${scope}/nexus:',
    ]);
    expect(suggestResources('${scope}/triple_store:g', context([])).map((s) => s.value)).toEqual([
      '${scope}/triple_store:graph/',
    ]);
    expect(suggestResources('${scope}:', context([]))).toEqual([]);
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
      { sid: 'Read', effect: 'Allow' as const, actions: ['triple_store:Query'], resources: ['abi:c:d/e'] },
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
        '      - "abi:c:d/e"',
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
    actions: [{ name: 'UseAgent', qualified: 'module:UseAgent', level: 'write', resource_types: ['agent'], creates: false, description: '' }],
    resource_types: [{ name: 'agent', id: 'path', placement: 'placed', container: false, personal: false, description: 'An agent of a module.' }],
  };
  const withModules = {
    catalogs: [...catalogs, moduleCatalog],
    actions: ['module:UseAgent'],
    modules: ['acme.people'],
    listed: { service: 'module', type: 'agent', module: 'acme.people', ids: [{ id: 'Recruiter', detail: 'Recruiter: Finds people.' }] },
  } as Parameters<typeof suggestResources>[1];

  it('suggests each module, then its agents from the listing', () => {
    expect(suggestResources('${scope}/module:agent/', withModules).map((s) => s.value)).toEqual([
      '${scope}/module:agent/*',
      '${scope}/module:agent/acme.people/',
    ]);
    const typed = suggestResources('${scope}/module:agent/acme.people/R', withModules);
    expect(typed).toEqual([
      { value: '${scope}/module:agent/acme.people/Recruiter', detail: 'Recruiter: Finds people.' },
    ]);
  });

  it('suggests only `*` without the listing of that step', () => {
    const context = { ...withModules, listed: { ...withModules.listed!, module: 'acme.market' } };
    expect(suggestResources('${scope}/module:agent/acme.people/', context).map((s) => s.value)).toEqual([
      '${scope}/module:agent/acme.people/*',
    ]);
  });

  it('knows which step is typed, for the listing', () => {
    expect(typedStep('${scope}/triple_store:graph/sa')).toEqual({ service: 'triple_store', type: 'graph', module: null, text: 'sa' });
    expect(typedStep(`${WS}/triple_store:graph/`)).toEqual({ service: 'triple_store', type: 'graph', module: null, text: '' });
    expect(typedStep('${scope}/module:agent/acme.people/R')).toEqual({ service: 'module', type: 'agent', module: 'acme.people', text: 'R' });
    expect(typedStep('${scope}/module:agent/acme')).toBeNull();
    expect(typedStep('${scope}/triple_store:')).toBeNull();
  });
});

describe('only what the caller may grant', () => {
  /** A user holding only agent A of acme.people and iam:CreatePolicy. */
  const onlyA: Publisher[] = [
    { id: 'engine', kind: 'engine', types: [publishedType('iam', 'policy', [['iam:CreatePolicy', ['${scope}/iam:policy/*']]])] },
    {
      id: 'acme.people',
      kind: 'module',
      types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/A']]], { module: 'acme.people' })],
    },
  ];

  it('suggests the actions they may grant and the patterns they may grant them on, nothing else', () => {
    const granted = grantableCatalogs(onlyA);
    expect(suggestActions('', granted).map((s) => s.value)).toEqual(['iam:CreatePolicy', 'module:UseAgent']);
    expect(suggestActions('triple_store:', granted)).toEqual([]);
    const context = {
      catalogs: granted,
      actions: ['module:UseAgent'],
      grantable: grantablePatterns(onlyA, ['module:UseAgent']),
      modules: ['acme.people'],
    };
    expect(suggestResources('', context).map((s) => s.value)).toEqual([
      '${scope}/module:agent/acme.people/A',
      'abi:',
      '${scope}/',
      '${scope}',
      '${principal.id}',
      '${user.id}',
      '${module.id}',
      '${module.project}',
    ]);
    expect(suggestResources('${scope}/', context).map((s) => s.value)).toEqual([
      '${scope}/module:agent/acme.people/A',
      '${scope}/module:',
    ]);
    expect(suggestResources('${scope}/module:agent/', context).map((s) => s.value)).toEqual([
      '${scope}/module:agent/acme.people/A',
      '${scope}/module:agent/*',
      '${scope}/module:agent/acme.people/',
    ]);
  });
});
