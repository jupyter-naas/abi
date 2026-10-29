import { describe, expect, it } from 'vitest';
import type { PolicyStatement, PublishersView } from '@/lib/iam-admin/types';
import { ORG, WS, adminPublishers, publishedType } from '../../access-fixtures';
import {
  atScope,
  belongsTo,
  grantableOn,
  builderPublishers,
  builderStatements,
  globMatches,
  refusedTypes,
  scopedName,
  splitStatements,
  wildcardProblem,
  type Choices,
} from './builder-model';

const keys = (view: PublishersView) => builderPublishers(view).flatMap((p) => p.types.map((t) => t.key));

describe('builderPublishers', () => {
  it('groups by publisher: the engine, naas_abi, then the modules by name', () => {
    const shuffled: PublishersView = {
      scope: WS,
      publishers: [...adminPublishers.publishers].reverse(),
    };
    const publishers = builderPublishers(shuffled);
    expect(publishers.map((p) => [p.id, p.label])).toEqual([
      ['engine', 'Engine'],
      ['naas_abi', 'naas_abi'],
      ['acme.market', 'acme.market'],
      ['acme.people', 'acme.people'],
    ]);
  });

  it('names each type and offers its grantable actions', () => {
    const [engine, naasAbi, , people] = builderPublishers(adminPublishers);
    const graph = engine.types.find((t) => t.key === 'triple_store:graph')!;
    expect(graph.label).toBe('Graphs');
    expect(graph.actions.map((a) => a.action)).toEqual(['triple_store:ListGraphs', 'triple_store:Query']);
    expect(graph.patterns).toEqual(['${scope}/triple_store:graph/*']);
    expect(naasAbi.types.map((t) => t.label)).toEqual(['Organizations', 'Workspaces', 'Features']);
    expect(builderPublishers({ scope: WS, publishers: [{ id: 'naas_abi', kind: 'naas_abi', types: [publishedType('nexus', 'role_features', [['nexus:X', ['${scope}/*']]])] }] })[0].types[0].label).toBe('Role features');
    // A module's agents are the `module` catalog's type under that module.
    expect(people.types.map((t) => [t.key, t.label, t.marker])).toEqual([
      ['module:agent@acme.people', 'Agents', 'module:agent/acme.people/'],
    ]);
  });

  it('offers nothing the caller may not grant', () => {
    expect(keys({ scope: WS, publishers: [] })).toEqual([]);
    const onlyA: PublishersView = {
      scope: WS,
      publishers: [
        {
          id: 'acme.people',
          kind: 'module',
          types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/A']]], { module: 'acme.people' })],
        },
      ],
    };
    expect(keys(onlyA)).toEqual(['module:agent@acme.people']);
  });
});

describe('resources', () => {
  const [engine, naasAbi, , people] = builderPublishers(adminPublishers);
  const graph = engine.types.find((t) => t.key === 'triple_store:graph')!;
  const workspace = naasAbi.types.find((t) => t.type === 'workspace')!;
  const agents = people.types[0];

  it('writes a listed resource at the scope', () => {
    expect(scopedName(`${WS}/triple_store:graph/sales`, WS)).toBe('${scope}/triple_store:graph/sales');
    expect(scopedName(`${ORG}/nexus:workspace/ws-1`, ORG)).toBe('${scope}/nexus:workspace/ws-1');
    expect(scopedName(WS, WS)).toBe('${scope}');
    expect(scopedName('abi:model_registry:model/gpt', 'abi:')).toBe('${scope}/model_registry:model/gpt');
    // Not under the scope: as named.
    expect(scopedName('abi:nexus:organization/other', ORG)).toBe('abi:nexus:organization/other');
  });

  it('tells which type a resource names', () => {
    expect(belongsTo(graph, '${scope}/triple_store:graph/sales')).toBe(true);
    expect(belongsTo(graph, '${scope}/triple_store:graph/sales-*')).toBe(true);
    expect(belongsTo(graph, '${scope}/nexus:workspace/ws-1/triple_store:graph/x')).toBe(true);
    expect(belongsTo(graph, '${scope}/triple_store:graph/x/nexus:feature/chat')).toBe(false);
    expect(belongsTo(graph, '${scope}/nexus:feature/chat')).toBe(false);
    expect(belongsTo(agents, '${scope}/module:agent/acme.people/Coach')).toBe(true);
    expect(belongsTo(agents, '${scope}/module:agent/acme.market/Analyst')).toBe(false);
    // What the caller may grant of a type is the type's, whatever it names.
    expect(belongsTo(workspace, '${scope}')).toBe(true);
  });

  it('lists only what the caller may grant of a type, as within a parent', () => {
    const features = naasAbi.types.find((t) => t.type === 'feature')!;
    expect(grantableOn(features, '${scope}/nexus:feature/chat')).toBe(true);
    expect(grantableOn(features, '${scope}/nexus:feature/code')).toBe(false);
    expect(grantableOn(agents, '${scope}/module:agent/acme.people/Coach')).toBe(true);
  });

  it('accepts a wildcard under ${scope}/ that names the type', () => {
    expect(wildcardProblem(graph, 'triple_store:graph/sales-*')).toBeNull();
    expect(wildcardProblem(graph, '*/triple_store:graph/*')).toBeNull();
    expect(wildcardProblem(graph, '')).toMatch(/Write a pattern/);
    expect(wildcardProblem(graph, 'nexus:feature/*')).toMatch(/triple_store:graph\//);
    expect(wildcardProblem(agents, 'module:agent/acme.people/*')).toBeNull();
    expect(wildcardProblem(agents, 'module:agent/*')).toMatch(/module:agent\/acme.people\//);
  });
});

describe('statements', () => {
  const publishers = builderPublishers(adminPublishers);

  it('writes one Allow per choice of actions and resources, and reads it back', () => {
    const choices: Choices = {
      'triple_store:graph': { actions: ['triple_store:Query', 'triple_store:ListGraphs'], resources: ['${scope}/triple_store:graph/sales', '${scope}/triple_store:graph/hr-*'] },
      'nexus:feature': { actions: ['nexus:UseFeature'], resources: ['${scope}/nexus:feature/chat'] },
      'module:agent@acme.people': { actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Coach'] },
    };
    const statements = builderStatements(publishers, choices);
    expect(statements).toEqual([
      {
        sid: 'TripleStoreListGraphsTripleStoreQuery',
        effect: 'Allow',
        // In the type's order of actions.
        actions: ['triple_store:ListGraphs', 'triple_store:Query'],
        resources: ['${scope}/triple_store:graph/sales', '${scope}/triple_store:graph/hr-*'],
      },
      { sid: 'NexusUseFeature', effect: 'Allow', actions: ['nexus:UseFeature'], resources: ['${scope}/nexus:feature/chat'] },
      { sid: 'ModuleUseAgent', effect: 'Allow', actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Coach'] },
    ]);
    const back = splitStatements(publishers, statements);
    expect(back.rest).toEqual([]);
    expect(back.choices).toEqual({
      'triple_store:graph': { actions: ['triple_store:ListGraphs', 'triple_store:Query'], resources: choices['triple_store:graph'].resources },
      'nexus:feature': choices['nexus:feature'],
      'module:agent@acme.people': choices['module:agent@acme.people'],
    });
    // Written again, the same document.
    expect(builderStatements(publishers, back.choices)).toEqual(statements);
  });

  it('writes nothing for a choice without actions or without resources', () => {
    expect(
      builderStatements(publishers, {
        'triple_store:graph': { actions: ['triple_store:Query'], resources: [] },
        'nexus:feature': { actions: [], resources: ['${scope}/nexus:feature/chat'] },
      }),
    ).toEqual([]);
  });

  it('gives every statement its own sid, never one a kept statement has', () => {
    const market = publishers.find((p) => p.id === 'acme.market')!.types[0];
    const kept: PolicyStatement[] = [{ sid: 'ModuleUseAgent', effect: 'Allow', actions: ['nexus:ListFiles'], resources: ['${scope}/nexus:file/*'] }];
    const statements = builderStatements(
      publishers,
      {
        [market.key]: { actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.market/Analyst'] },
        'module:agent@acme.people': { actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Coach'] },
      },
      kept,
    );
    expect(statements.map((s) => s.sid)).toEqual(['ModuleUseAgent2', 'ModuleUseAgent3']);
    for (const sid of statements.map((s) => s.sid!)) expect(sid).toMatch(/^[A-Za-z0-9]{1,64}$/);
  });

  it('keeps what the builder cannot show as statements of their own', () => {
    const deny: PolicyStatement = { effect: 'Deny', actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/hr'] };
    const notGrantable: PolicyStatement = { effect: 'Allow', actions: ['triple_store:DropGraph'], resources: ['${scope}/triple_store:graph/*'] };
    const twoTypes: PolicyStatement = {
      effect: 'Allow',
      actions: ['triple_store:Query', 'nexus:UseFeature'],
      resources: ['${scope}/triple_store:graph/*', '${scope}/nexus:feature/chat'],
    };
    const wildcardAction: PolicyStatement = { effect: 'Allow', actions: ['triple_store:*'], resources: ['${scope}/triple_store:graph/*'] };
    const otherType: PolicyStatement = { effect: 'Allow', actions: ['triple_store:Query'], resources: ['${scope}/nexus:feature/chat'] };
    const query: PolicyStatement = { sid: 'Q', effect: 'Allow', actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/a'] };
    // A second choice of the same type: kept as written.
    const again: PolicyStatement = { effect: 'Allow', actions: ['triple_store:ListGraphs'], resources: ['${scope}/triple_store:graph/b'] };
    const back = splitStatements(publishers, [deny, notGrantable, twoTypes, wildcardAction, otherType, query, again]);
    expect(back.choices).toEqual({ 'triple_store:graph': { actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/a'] } });
    expect(back.rest).toEqual([deny, notGrantable, twoTypes, wildcardAction, otherType, again]);
  });

  it('reads a pattern the caller may grant back into its type', () => {
    const everything = builderPublishers({
      scope: WS,
      publishers: [{ id: 'engine', kind: 'engine', types: [publishedType('triple_store', 'graph', [['triple_store:Query', ['${scope}/*']]])] }],
    });
    const back = splitStatements(everything, [{ effect: 'Allow', actions: ['triple_store:Query'], resources: ['${scope}/*'] }]);
    expect(back.choices['triple_store:graph']?.resources).toEqual(['${scope}/*']);
  });
});

describe('sub-policies', () => {
  it('offers within a parent what the API returns for it, and keeps the rest as statements', () => {
    // `/publishers?parent=` of "O access" (agents of acme.people, chat): nothing of the engine.
    const within: PublishersView = {
      scope: WS,
      publishers: adminPublishers.publishers
        .filter((p) => p.id !== 'engine' && p.id !== 'acme.market')
        .map((p) => (p.id === 'naas_abi' ? { ...p, types: p.types.filter((t) => t.type === 'feature') } : p)),
    };
    const publishers = builderPublishers(within);
    expect(publishers.map((p) => p.id)).toEqual(['naas_abi', 'acme.people']);
    const graphs: PolicyStatement = { effect: 'Allow', actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/*'] };
    const chat: PolicyStatement = { effect: 'Allow', actions: ['nexus:UseFeature'], resources: ['${scope}/nexus:feature/chat'] };
    const back = splitStatements(publishers, [graphs, chat]);
    expect(Object.keys(back.choices)).toEqual(['nexus:feature']);
    expect(back.rest).toEqual([graphs]);
  });
});

describe('refusedTypes', () => {
  const publishers = builderPublishers(adminPublishers);
  const choices: Choices = {
    'module:agent@acme.people': { actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Coach'] },
    'nexus:feature': { actions: ['nexus:UseFeature'], resources: ['${scope}/nexus:feature/chat'] },
  };

  it('names the type IAM refused, as written in the policy or at the scope', () => {
    const asWritten = `You cannot grant what you do not hold: statement 0 (ModuleUseAgent) of a new policy allows module:UseAgent on \${scope}/module:agent/acme.people/Coach at ${WS}, and you do not hold it there`;
    expect(refusedTypes(publishers, choices, asWritten, WS)).toEqual(['module:agent@acme.people']);
    const placed = `You cannot grant what you do not hold: statement 1 allows nexus:UseFeature on ${WS}/nexus:feature/chat at ${WS}, and you do not hold it there`;
    expect(refusedTypes(publishers, choices, placed, WS)).toEqual(['nexus:feature']);
    expect(refusedTypes(publishers, choices, 'You do not have permission to do this.', WS)).toEqual([]);
  });
});

describe('patterns', () => {
  it('reads IAM patterns: * any run, ? one character, the rest literally', () => {
    expect(globMatches('${scope}/module:agent/*', '${scope}/module:agent/acme.people/Recruiter')).toBe(true);
    expect(globMatches('${scope}/module:agent/acme.?eople/*', '${scope}/module:agent/acme.people/Coach')).toBe(true);
    expect(globMatches('${scope}/module:app/*', '${scope}/module:agent/acme.people/Coach')).toBe(false);
  });

  it('reads a pattern written at a scope where it is attached', () => {
    expect(atScope('${scope}/module:agent/acme.people/*', WS)).toBe(`${WS}/module:agent/acme.people/*`);
    expect(atScope('${scope}', WS)).toBe(WS);
    expect(atScope('${scope}/triple_store:graph/*', `${ORG}/*`)).toBe(`${ORG}/triple_store:graph/*`);
    expect(atScope('${scope}/nexus:feature/chat', 'abi:')).toBe('abi:nexus:feature/chat');
  });
});
