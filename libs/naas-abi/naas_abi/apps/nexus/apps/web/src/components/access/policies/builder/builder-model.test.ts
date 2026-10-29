import { describe, expect, it } from 'vitest';
import type { GrantableView, ModuleScopesEntry } from '@/lib/iam-admin/types';
import {
  atScope,
  builderGroups,
  builderStatements,
  globMatches,
  refusedItems,
  splitStatements,
} from './builder-model';

/** The workspace w of the organization o, as IAM names it. */
const W = 'abi:nexus:organization/o/nexus:workspace/w';

const people: ModuleScopesEntry = {
  module: 'acme.people',
  agents: [
    { name: 'Recruiter', display_name: 'Recruiter', description: 'Finds people', icon: null, resource: '${scope}/module:agent/acme.people/Recruiter', actions: ['module:UseAgent'] },
    { name: 'Coach', display_name: 'Coach', description: '', icon: null, resource: '${scope}/module:agent/acme.people/Coach', actions: ['module:UseAgent'] },
  ],
  apps: [],
  workflows: [
    {
      name: 'workflow.sync',
      display_name: 'Sync',
      description: '',
      icon: null,
      resource: '${scope}/module:workflow/acme.people/workflow.sync',
      actions: ['module:RunWorkflow', 'module:ReadWorkflowRuns'],
    },
  ],
  pipelines: [],
  declared: {
    service: 'acme_people',
    version: 1,
    resource_types: [{ name: 'profile', description: 'A profile', resource: '${scope}/acme_people:profile/*' }],
    actions: [{ action: 'acme_people:Export', level: 'read', resource_types: ['profile'], description: 'Export profiles' }],
  },
};

const market: ModuleScopesEntry = {
  module: 'acme.market',
  agents: [{ name: 'Analyst', display_name: 'Analyst', description: '', icon: null, resource: '${scope}/module:agent/acme.market/Analyst', actions: ['module:UseAgent'] }],
  apps: [],
  workflows: [],
  pipelines: [],
  declared: null,
};

/** A workspace admin whose workspace's set has acme.people only. */
const admin: GrantableView = {
  scope: W,
  catalogs: [
    {
      service: 'module',
      actions: [
        { action: 'module:UseAgent', resources: ['${scope}/module:agent/acme.people/*'], excluded: [] },
        { action: 'module:RunWorkflow', resources: ['${scope}/module:workflow/acme.people/*'], excluded: [] },
        { action: 'module:ReadWorkflowRuns', resources: ['${scope}/module:workflow/acme.people/*'], excluded: [] },
      ],
    },
    { service: 'acme_people', actions: [{ action: 'acme_people:Export', resources: ['${scope}/acme_people:*'], excluded: [] }] },
    {
      service: 'nexus',
      actions: [{ action: 'nexus:UseFeature', resources: ['${scope}/nexus:feature/chat', '${scope}/nexus:feature/files'], excluded: [] }],
    },
  ],
};

const keys = (groups: ReturnType<typeof builderGroups>) =>
  groups.flatMap((g) => g.sections.flatMap((s) => s.items.map((i) => i.key)));

describe('globMatches', () => {
  it('reads IAM patterns: * any run, ? one character, the rest literally', () => {
    expect(globMatches('${scope}/module:agent/*', '${scope}/module:agent/acme.people/Recruiter')).toBe(true);
    expect(globMatches('${scope}/module:agent/acme.?eople/*', '${scope}/module:agent/acme.people/Coach')).toBe(true);
    expect(globMatches('${scope}/module:app/*', '${scope}/module:agent/acme.people/Coach')).toBe(false);
    expect(globMatches('*', 'anything')).toBe(true);
  });
});

describe('builderGroups', () => {
  it('offers, per module and for Nexus features, only what the caller may grant', () => {
    const groups = builderGroups(admin, [people, market], ['chat', 'files', 'apps']);
    expect(groups.map((g) => g.label)).toEqual(['acme.people', 'Nexus features']);
    expect(keys(groups)).toEqual([
      'module:agent/acme.people/Coach',
      'module:agent/acme.people/Recruiter',
      'module:workflow/acme.people/workflow.sync',
      'declared:acme_people:Export@${scope}/acme_people:profile/*',
      'feature:chat',
      'feature:files',
    ]);
    const sync = groups[0].sections.find((s) => s.id === 'workflows')?.items[0];
    expect(sync?.actions).toEqual(['module:RunWorkflow', 'module:ReadWorkflowRuns']);
  });

  it('grants only the actions of an item the caller holds', () => {
    const runsOnly: GrantableView = {
      scope: W,
      catalogs: [{ service: 'module', actions: [{ action: 'module:ReadWorkflowRuns', resources: ['${scope}/module:workflow/*'], excluded: [] }] }],
    };
    const [group] = builderGroups(runsOnly, [people], []);
    expect(group.sections.map((s) => s.id)).toEqual(['workflows']);
    expect(group.sections[0].items[0].actions).toEqual(['module:ReadWorkflowRuns']);
  });

  it('leaves out what a Deny takes back', () => {
    const denied: GrantableView = {
      scope: W,
      catalogs: [
        {
          service: 'module',
          actions: [{ action: 'module:UseAgent', resources: ['${scope}/module:agent/*'], excluded: ['${scope}/module:agent/acme.people/Coach'] }],
        },
      ],
    };
    expect(keys(builderGroups(denied, [people, market], []))).toEqual([
      'module:agent/acme.people/Recruiter',
      'module:agent/acme.market/Analyst',
    ]);
  });

  it('offers every known feature to whoever holds them all, and nothing to a stranger', () => {
    const everything: GrantableView = { scope: 'abi:', catalogs: [{ service: 'nexus', actions: [{ action: 'nexus:UseFeature', resources: ['${scope}/*'], excluded: [] }] }] };
    expect(keys(builderGroups(everything, [], ['chat', 'apps']))).toEqual(['feature:apps', 'feature:chat']);
    expect(builderGroups({ scope: W, catalogs: [] }, [people, market], ['chat'])).toEqual([]);
  });
});

describe('statements', () => {
  const groups = builderGroups(admin, [people, market], ['chat', 'files']);

  it('writes one Allow per set of actions, and reads it back', () => {
    const selected = new Set(['module:agent/acme.people/Recruiter', 'module:workflow/acme.people/workflow.sync', 'feature:chat']);
    const statements = builderStatements(groups, selected);
    expect(statements).toEqual([
      { sid: 'ModuleUseAgent', effect: 'Allow', actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Recruiter'] },
      {
        sid: 'ModuleRunWorkflowModuleReadWorkflowRuns',
        effect: 'Allow',
        actions: ['module:RunWorkflow', 'module:ReadWorkflowRuns'],
        resources: ['${scope}/module:workflow/acme.people/workflow.sync'],
      },
      { sid: 'NexusUseFeature', effect: 'Allow', actions: ['nexus:UseFeature'], resources: ['${scope}/nexus:feature/chat'] },
    ]);
    const back = splitStatements(groups, statements);
    expect([...back.selected].sort()).toEqual([...selected].sort());
    expect(back.rest).toEqual([]);
  });

  it('gives every statement its own sid, never one a kept statement has', () => {
    const crm: ModuleScopesEntry = {
      ...market,
      module: 'crm',
      agents: [],
      declared: {
        service: 'crm',
        version: 1,
        resource_types: [{ name: 'record', description: '', resource: '${scope}/crm:record/*' }],
        actions: [{ action: 'crm:Query', level: 'read', resource_types: ['record'], description: '' }],
      },
    };
    const erp: ModuleScopesEntry = {
      ...crm,
      module: 'erp',
      declared: { ...crm.declared!, service: 'erp', resource_types: [{ name: 'record', description: '', resource: '${scope}/erp:record/*' }], actions: [{ action: 'erp:Query', level: 'read', resource_types: ['record'], description: '' }] },
    };
    const both: GrantableView = {
      scope: W,
      catalogs: [
        { service: 'crm', actions: [{ action: 'crm:Query', resources: ['${scope}/crm:*'], excluded: [] }] },
        { service: 'erp', actions: [{ action: 'erp:Query', resources: ['${scope}/erp:*'], excluded: [] }] },
        ...admin.catalogs,
      ],
    };
    const offered = builderGroups(both, [people, crm, erp], []);
    const kept = [{ sid: 'ModuleUseAgent', effect: 'Allow' as const, actions: ['nexus:ListFiles'], resources: ['${scope}/nexus:file/*'] }];
    const statements = builderStatements(
      offered,
      new Set(['declared:crm:Query@${scope}/crm:record/*', 'declared:erp:Query@${scope}/erp:record/*', 'module:agent/acme.people/Coach']),
      kept,
    );
    expect(statements.map((s) => s.sid)).toEqual(['ModuleUseAgent2', 'CrmQuery', 'ErpQuery']);
    for (const sid of statements.map((s) => s.sid!)) expect(sid).toMatch(/^[A-Za-z0-9]{1,64}$/);
  });

  it('keeps what the builder cannot show as statements of their own', () => {
    const other = { effect: 'Allow' as const, actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/*'] };
    const deny = { effect: 'Deny' as const, actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Coach'] };
    const partial = { effect: 'Allow' as const, actions: ['module:RunWorkflow'], resources: ['${scope}/module:workflow/acme.people/workflow.sync'] };
    const agent = { effect: 'Allow' as const, actions: ['module:UseAgent'], resources: ['${scope}/module:agent/acme.people/Coach'] };
    const back = splitStatements(groups, [other, deny, partial, agent]);
    expect([...back.selected]).toEqual(['module:agent/acme.people/Coach']);
    expect(back.rest).toEqual([other, deny, partial]);
  });
});

describe('refusedItems', () => {
  const groups = builderGroups(admin, [people, market], ['chat']);

  it('names the item IAM refused, as written in the policy or at the scope', () => {
    const asWritten = `You cannot grant what you do not hold: statement 0 (UseAgent) of a new policy allows module:UseAgent on \${scope}/module:agent/acme.people/Recruiter at ${W}, and the set of workspace w does not include it`;
    expect(refusedItems(groups, asWritten, W)).toEqual(['module:agent/acme.people/Recruiter']);
    const placed = `You cannot grant what you do not hold: statement 1 allows nexus:UseFeature on ${W}/nexus:feature/chat at ${W}, and you do not hold it there`;
    expect(refusedItems(groups, placed, W)).toEqual(['feature:chat']);
    const below = `You cannot grant what you do not hold: statement 1 allows nexus:UseFeature on ${W}/nexus:feature/chat at ${W}/*, and you do not hold it there`;
    expect(refusedItems(groups, below, W)).toEqual(['feature:chat']);
    const platform = 'You cannot grant what you do not hold: statement 1 allows nexus:UseFeature on abi:nexus:feature/chat at abi:, and you do not hold it there';
    expect(refusedItems(groups, platform, 'abi:')).toEqual(['feature:chat']);
    expect(refusedItems(groups, 'You do not have permission to do this.', W)).toEqual([]);
  });
});

describe('atScope', () => {
  it('reads a pattern written at a scope where it is attached', () => {
    expect(atScope('${scope}/module:agent/acme.people/*', W)).toBe(`${W}/module:agent/acme.people/*`);
    expect(atScope('${scope}', W)).toBe(W);
    expect(atScope('${scope}/triple_store:graph/*', 'abi:nexus:organization/o/*')).toBe(
      'abi:nexus:organization/o/triple_store:graph/*',
    );
    // At the platform `${scope}/` reads `abi:`.
    expect(atScope('${scope}/nexus:feature/chat', 'abi:')).toBe('abi:nexus:feature/chat');
    expect(atScope('abi:triple_store:graph/x', W)).toBe('abi:triple_store:graph/x');
  });
});

describe('the new grammar', () => {
  it('writes the builder choices as `${scope}/` patterns, never `${scope}:`', () => {
    const groups = builderGroups(admin, [people, market], ['chat']);
    const statements = builderStatements(groups, new Set(keys(groups)));
    const resources = statements.flatMap((s) => s.resources);
    expect(resources.length).toBeGreaterThan(0);
    expect(resources.every((r) => r.startsWith('${scope}/'))).toBe(true);
    expect(resources).toContain('${scope}/acme_people:profile/*');
    expect(resources).toContain('${scope}/nexus:feature/files');
  });

  it('falls back to `${scope}/<service>:<type>/*` for a declared type without a pattern', () => {
    const bare: ModuleScopesEntry = {
      ...market,
      module: 'acme.bare',
      agents: [],
      declared: {
        service: 'acme_bare',
        version: 1,
        resource_types: [],
        actions: [{ action: 'acme_bare:Read', level: 'read', resource_types: ['thing'], description: '' }],
      },
    };
    const grantable: GrantableView = {
      scope: W,
      catalogs: [{ service: 'acme_bare', actions: [{ action: 'acme_bare:Read', resources: ['${scope}/acme_bare:*'], excluded: [] }] }],
    };
    expect(keys(builderGroups(grantable, [bare], []))).toEqual(['declared:acme_bare:Read@${scope}/acme_bare:thing/*']);
  });
});
