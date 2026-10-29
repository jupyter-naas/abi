// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { PolicyDocument } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { EMPTY_DIRECTORY } from '../access-directory';
import { PLATFORM_ACCESS_SCOPE, type AccessScope } from '../access-scope';
import type { PublishersView, ResourceQuery } from '@/lib/iam-admin/types';
import {
  ORG,
  WS,
  adminPublishers,
  fakeApi,
  managedPolicy,
  publishedType,
  readerPolicy,
  resourcePage,
  wsScope,
} from '../access-fixtures';
import { PoliciesView } from './policies';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const field = (label: string) => document.querySelector(`[aria-label="${label}"]`);
/** Past the editor's validation delay, so IAM has answered. */
const validated = async () => {
  await new Promise((resolve) => setTimeout(resolve, 400));
  await mounted!.flush();
};

/** What the caller may list: graphs sales and hr, the org's workspace ws-1, chat and files, the
 *  agents of each module. */
function listing(query: ResourceQuery) {
  const key = query.module ? `${query.service}:${query.type}@${query.module}` : `${query.service}:${query.type}`;
  const items: Record<string, [string, string][]> = {
    'triple_store:graph': [
      ['sales', 'Sales'],
      ['hr', 'HR'],
    ],
    'nexus:feature': [
      ['chat', 'Chat'],
      ['files', 'Files'],
    ],
    'module:agent@acme.people': [
      ['acme.people/Recruiter', 'Recruiter'],
      ['acme.people/Coach', 'Coach'],
    ],
    'module:agent@acme.market': [['acme.market/Analyst', 'Analyst']],
  };
  const found = (items[key] ?? []).filter(([, label]) => label.toLowerCase().includes((query.q ?? '').toLowerCase()));
  return resourcePage(query.service, query.type, found, { listed: key in items });
}

function fake(over: Record<string, unknown> = {}) {
  return fakeApi({
    listPolicies: vi.fn().mockResolvedValue({ items: [managedPolicy, readerPolicy], next_after: null }),
    publishers: vi.fn().mockResolvedValue(adminPublishers),
    resources: vi.fn((query: ResourceQuery) => Promise.resolve(listing(query))),
    validatePolicy: vi.fn((source: { document: PolicyDocument }) =>
      Promise.resolve({ valid: true, errors: [], document: source.document }),
    ),
    ...over,
  });
}

async function open(can: (a: string) => boolean, over: Record<string, unknown> = {}, scope: AccessScope = PLATFORM_ACCESS_SCOPE) {
  const api = fake(over);
  mounted = await mount(PoliciesView, { api, can, scope, directory: EMPTY_DIRECTORY });
  await mounted.flush();
  return api;
}

describe('PoliciesView', () => {
  it('lists policies and marks the managed ones', async () => {
    await open(() => true);
    const managed = document.querySelector('[data-policy="builtin.viewer"]');
    expect(managed?.textContent).toContain('managed');
    expect(document.querySelector('[data-policy="pol_1"]')?.textContent).toContain('Graph reader');
    expect(document.querySelector('[aria-label="Delete Viewer"]')).toBeNull();
    expect(document.querySelector('[aria-label="Delete Graph reader"]')).not.toBeNull();
  });

  it('opens a managed policy read-only', async () => {
    await open(() => true);
    await mounted!.click(document.querySelector('[data-policy="builtin.viewer"] button'));
    expect(mounted!.host.textContent).toContain('Managed: IAM writes this policy');
    expect(button('Save changes')).toBeUndefined();
  });

  it('asks before deleting, then deletes and reloads', async () => {
    const deletePolicy = vi.fn().mockResolvedValue(undefined);
    await open(() => true, { deletePolicy });
    await mounted!.click(document.querySelector('[aria-label="Delete Graph reader"]'));
    expect(deletePolicy).not.toHaveBeenCalled();
    await mounted!.click(button('Confirm delete') ?? null);
    expect(deletePolicy).toHaveBeenCalledWith('pol_1');
  });

  it('shows no create or delete to a caller who may not', async () => {
    const api = await open((action) => action === 'iam:ListPolicies');
    expect(button('New policy')).toBeUndefined();
    expect(document.querySelector('[aria-label="Delete Graph reader"]')).toBeNull();
    await mounted!.click(document.querySelector('[data-policy="pol_1"] button'));
    expect(button('Save changes')).toBeUndefined();
    expect(mounted!.host.textContent).toContain('Read only');
    expect(api.publishers).not.toHaveBeenCalled();
  });

  it('says why the list could not load', async () => {
    await open(() => true, { listPolicies: vi.fn().mockRejectedValue(new Error('You do not have permission')) });
    expect(mounted!.host.textContent).toContain('You do not have permission');
  });
});

describe('PoliciesView at a workspace', () => {
  const owned = { ...readerPolicy, id: 'pol_ws', name: 'Recruiters', owner_scope: WS };
  const fromOrg = { ...readerPolicy, id: 'pol_org', name: 'Org readers', owner_scope: ORG };
  const listed = { listPolicies: vi.fn().mockResolvedValue({ items: [owned, fromOrg], next_after: null }) };
  const check = async (label: string) => mounted!.click(field(label));
  const expand = async (title: string) => {
    await mounted!.click(field(`Open ${title}`));
    await validated();
  };
  const newPolicy = async (name: string) => {
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    await mounted!.type(field('Policy name'), name);
  };

  it('lists the level’s own and, read-only, those it may attach from above', async () => {
    const api = await open(() => true, listed, wsScope);
    expect(api.listPolicies).toHaveBeenCalledWith(undefined, WS);
    expect(document.querySelector('[data-policy="pol_org"]')?.textContent).toContain('Organization acme');
    expect(document.querySelector('[aria-label="Delete Org readers"]')).toBeNull();
    expect(document.querySelector('[aria-label="Delete Recruiters"]')).not.toBeNull();
    await mounted!.click(document.querySelector('[data-policy="pol_org"] button'));
    expect(mounted!.host.textContent).toContain('Read only');
  });

  it('offers by publisher: the engine, naas_abi, then the modules', async () => {
    const api = await open(() => true, listed, wsScope);
    await newPolicy('Anything');
    expect(api.publishers).toHaveBeenCalledWith(WS, null, { derive: false });
    const publishers = [...document.querySelectorAll('[data-builder-publisher]')].map((e) => e.getAttribute('data-builder-publisher'));
    expect(publishers).toEqual(['engine', 'naas_abi', 'acme.market', 'acme.people']);
    const naasAbi = document.querySelector('[data-builder-publisher="naas_abi"]');
    expect([...naasAbi!.querySelectorAll('[data-builder-type]')].map((e) => e.getAttribute('data-builder-type'))).toEqual([
      'nexus:organization',
      'nexus:workspace',
      'nexus:feature',
    ]);
  });

  it('lists the workspace itself at the workspace, once', async () => {
    const resources = vi.fn((query: ResourceQuery) =>
      Promise.resolve(
        query.type === 'workspace'
          ? { ...resourcePage('nexus', 'workspace', []), items: [{ name: WS, id: 'ws-1', label: 'Alpha', description: '' }] }
          : listing(query),
      ),
    );
    await open(() => true, { ...listed, resources }, wsScope);
    await newPolicy('Alpha readers');
    await expand('Workspaces');
    const boxes = [...document.querySelectorAll('[data-builder-type="nexus:workspace"] input[type="checkbox"]')].map((e) =>
      e.getAttribute('aria-label'),
    );
    expect(boxes).toEqual(['Workspaces: GetWorkspace', 'Workspaces: Alpha']);
    expect(document.querySelector('[data-builder-resource="${scope}"]')).not.toBeNull();
  });

  it('builds a policy of a type’s actions and resources picked from the listing, owned by the workspace', async () => {
    const createPolicy = vi.fn((input: { document: PolicyDocument }) => Promise.resolve({ ...owned, document: input.document }));
    const api = await open(() => true, { ...listed, createPolicy }, wsScope);
    await newPolicy('Readers');
    await expand('Graphs');
    expect(api.resources).toHaveBeenCalledWith(expect.objectContaining({ scope: WS, service: 'triple_store', type: 'graph' }));
    // The graph type's actions, and the graphs the caller may list.
    expect(field('Graphs: ListGraphs')).not.toBeNull();
    expect(field('Graphs: DropGraph')).toBeNull();
    await check('Graphs: Query');
    await check('Graphs: Sales');
    // Searched as typed.
    await mounted!.type(field('Search Graphs'), 'h');
    await validated();
    expect(api.resources).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'h' }));
    expect(field('Graphs: Sales')).toBeNull();
    await check('Graphs: HR');
    await validated();
    expect(api.validatePolicy).toHaveBeenLastCalledWith(expect.anything(), WS);
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();

    expect(createPolicy).toHaveBeenCalledWith({
      document: {
        version: '2026-10-13',
        statements: [
          {
            sid: 'TripleStoreQuery',
            effect: 'Allow',
            actions: ['triple_store:Query'],
            resources: ['${scope}/triple_store:graph/sales', '${scope}/triple_store:graph/hr'],
          },
        ],
      },
      name: 'Readers',
      description: '',
      scope: WS,
    });
  });

  it('accepts a wildcard once IAM validates it', async () => {
    const createPolicy = vi.fn((input: { document: PolicyDocument }) => Promise.resolve({ ...owned, document: input.document }));
    const api = await open(() => true, { ...listed, createPolicy }, wsScope);
    await newPolicy('Sales graphs');
    await expand('Graphs');
    await check('Graphs: Query');
    await mounted!.type(field('Wildcard of Graphs'), 'nexus:feature/*');
    expect(document.querySelector('[data-wildcard-verdict]')?.textContent).toContain('ends with triple_store:graph/');
    expect(button('Add pattern')?.disabled).toBe(true);
    await mounted!.type(field('Wildcard of Graphs'), 'triple_store:graph/sales-*');
    await validated();
    expect(api.validatePolicy).toHaveBeenCalledWith(
      {
        document: {
          version: '2026-10-13',
          statements: [{ effect: 'Allow', actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/sales-*'] }],
        },
      },
      WS,
    );
    expect(document.querySelector('[data-wildcard-verdict]')?.textContent).toBe('Valid pattern.');
    await mounted!.click(button('Add pattern') ?? null);
    expect(document.querySelector('[aria-label="Chosen patterns of Graphs"]')?.textContent).toContain(
      '${scope}/triple_store:graph/sales-*',
    );
    await validated();
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();
    expect(createPolicy.mock.calls[0][0].document.statements).toEqual([
      { sid: 'TripleStoreQuery', effect: 'Allow', actions: ['triple_store:Query'], resources: ['${scope}/triple_store:graph/sales-*'] },
    ]);
  });

  it('shows a policy written in the builder with the same choices when reopened', async () => {
    const created: { document?: PolicyDocument } = {};
    const createPolicy = vi.fn((input: { document: PolicyDocument; name: string }) => {
      created.document = input.document;
      return Promise.resolve({ ...owned, id: 'pol_new', name: input.name, document: input.document });
    });
    await open(() => true, { ...listed, createPolicy }, wsScope);
    await newPolicy('Coaches');
    await expand('acme.people Agents');
    await check('acme.people Agents: UseAgent');
    await check('acme.people Agents: Coach');
    await expand('Features');
    await check('Features: UseFeature');
    await check('Features: Chat');
    await validated();
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();
    await validated();

    // Reopened (the saved policy is selected): in the builder, the same boxes ticked.
    expect(document.querySelector('[role="tab"][aria-selected="true"]')?.textContent).toBe('Builder');
    for (const label of ['acme.people Agents: UseAgent', 'acme.people Agents: Coach', 'Features: UseFeature', 'Features: Chat']) {
      expect((field(label) as HTMLInputElement | null)?.checked, label).toBe(true);
    }
    expect((field('acme.people Agents: Recruiter') as HTMLInputElement).checked).toBe(false);
    expect(created.document?.statements.map((s) => s.resources)).toEqual([
      ['${scope}/nexus:feature/chat'],
      ['${scope}/module:agent/acme.people/Coach'],
    ]);
  });

  it('empties the policy when the start goes back to Nothing', async () => {
    const member = {
      ...managedPolicy,
      id: 'builtin.member',
      document: { version: '2026-10-13', statements: [{ effect: 'Allow' as const, actions: ['nexus:ListFiles'], resources: ['${scope}/nexus:file/*'] }] },
    };
    await open(() => true, { listPolicies: vi.fn().mockResolvedValue({ items: [owned, member], next_after: null }) }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    const start = field('Start from a built-in role') as HTMLSelectElement;
    for (const value of ['builtin.member', '']) {
      start.value = value;
      start.dispatchEvent(new Event('change', { bubbles: true }));
      await mounted!.flush();
    }
    expect(mounted!.host.textContent).not.toContain('other statement');
    await mounted!.click([...document.querySelectorAll('[role="tab"]')].find((t) => t.textContent === 'Statements') ?? null);
    expect(document.querySelectorAll('[aria-label^="Add to actions of statement"]')).toHaveLength(0);
  });

  it('keeps what was typed when the builder arrives after the editor opened', async () => {
    let arrive: (view: PublishersView) => void = () => undefined;
    const publishers = vi.fn(() => new Promise((resolve) => (arrive = resolve)));
    await open(() => true, { ...listed, publishers }, wsScope);
    await newPolicy('Recruiters');
    arrive(adminPublishers);
    await mounted!.flush();

    expect((field('Policy name') as HTMLInputElement).value).toBe('Recruiters');
    expect(document.querySelector('[data-builder-type="module:agent@acme.people"]')).not.toBeNull();
  });

  it('shows IAM’s refusal beside the type it names', async () => {
    const refusal =
      `You cannot grant what you do not hold: statement 0 (ModuleUseAgent) allows module:UseAgent on \${scope}/module:agent/acme.people/Coach at ${WS}, and you do not hold it there`;
    const createPolicy = vi.fn().mockRejectedValue(new IamAdminError(refusal, 403));
    await open(() => true, { ...listed, createPolicy }, wsScope);
    await newPolicy('Coaches');
    await expand('acme.people Agents');
    await check('acme.people Agents: UseAgent');
    await check('acme.people Agents: Coach');
    await validated();
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();

    const type = document.querySelector('[data-builder-type="module:agent@acme.people"]');
    expect(type?.querySelector('[role="alert"]')?.textContent).toBe(refusal);
    expect(document.querySelector('[data-builder-type="module:agent@acme.market"] [role="alert"]')).toBeNull();
    // Valid is not granted: no green line beside the refusal.
    expect(mounted!.host.textContent).not.toContain('Valid policy.');
  });

  it('starts from a built-in role the caller’s list holds, and offers none other', async () => {
    const member = {
      ...managedPolicy,
      id: 'builtin.member',
      document: { version: '2026-10-13', statements: [{ effect: 'Allow' as const, actions: ['nexus:ListFiles'], resources: ['${scope}/nexus:file/*'] }] },
    };
    await open(() => true, { listPolicies: vi.fn().mockResolvedValue({ items: [owned, member], next_after: null }) }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    const start = field('Start from a built-in role') as HTMLSelectElement;
    expect([...start.options].map((o) => o.value)).toEqual(['', 'builtin.member']);
    start.value = 'builtin.member';
    start.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();

    expect(mounted!.host.textContent).toContain('1 other statement stays as written');
  });
});

describe('PoliciesView sub-policies', () => {
  const oAccess = { ...readerPolicy, id: 'pol_o', name: 'O access', owner_scope: 'abi:' };
  const analysts = { ...readerPolicy, id: 'pol_w', name: 'W analysts', owner_scope: WS, parent_id: 'pol_o' };
  const listed = { listPolicies: vi.fn().mockResolvedValue({ items: [analysts, oAccess], next_after: null }) };
  /** `/publishers?parent=pol_o`: within "O access", acme.people's agents and chat only. */
  const withinO: PublishersView = {
    scope: WS,
    publishers: [
      { id: 'naas_abi', kind: 'naas_abi', types: [publishedType('nexus', 'feature', [['nexus:UseFeature', ['${scope}/nexus:feature/chat']]])] },
      {
        id: 'acme.people',
        kind: 'module',
        types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/*']]], { module: 'acme.people' })],
      },
    ],
  };
  const publishers = vi.fn((_scope: string, parent?: string | null) => Promise.resolve(parent === 'pol_o' ? withinO : adminPublishers));

  it('shows the policies as a tree of parents and sub-policies', async () => {
    await open(() => true, listed, wsScope);
    const rows = [...document.querySelectorAll('[data-policy]')].map((r) => [r.getAttribute('data-policy'), r.getAttribute('data-depth')]);
    expect(rows).toEqual([
      ['pol_o', '0'],
      ['pol_w', '1'],
    ]);
    expect(document.querySelector('[data-policy="pol_w"] [aria-label="Sub-policy"]')).not.toBeNull();
  });

  it('creates a sub-policy offering only what the parent has, saved with its parent', async () => {
    const createPolicy = vi.fn((input: { document: PolicyDocument; name: string }) =>
      Promise.resolve({ ...analysts, id: 'pol_new', name: input.name, document: input.document, parent_id: 'pol_o' }),
    );
    await open(() => true, { ...listed, publishers, createPolicy }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    await mounted!.type(field('Policy name'), 'Analysts');
    const parent = field('Sub-policy of') as HTMLSelectElement;
    // Managed policies are offered as roles to start from, not as parents.
    expect([...parent.options].map((o) => o.value)).toEqual(['', 'pol_w', 'pol_o']);
    parent.value = 'pol_o';
    parent.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();

    // A new sub-policy: IAM judges the parent as creating it would.
    expect(publishers).toHaveBeenLastCalledWith(WS, 'pol_o', { derive: true });
    const offered = [...document.querySelectorAll('[data-builder-publisher]')].map((e) => e.getAttribute('data-builder-publisher'));
    expect(offered).toEqual(['naas_abi', 'acme.people']);
    await mounted!.click(field('Open acme.people Agents'));
    await validated();
    await mounted!.click(field('acme.people Agents: UseAgent'));
    await mounted!.click(field('acme.people Agents: Recruiter'));
    await validated();
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();

    expect(createPolicy).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Analysts', scope: WS, parent: 'pol_o' }),
    );
  });

  it('shows IAM’s refusal of a parent the caller may read but not derive from', async () => {
    // A W admin who is not an O admin reads "O access" (listed here), and may not derive from it.
    const refusal = `You derive only from a policy attached to you or to one of your groups at ${WS} or above: pol_o is not`;
    const refusing = vi.fn((_scope: string, parent?: string | null, options?: { derive?: boolean }) =>
      parent && options?.derive ? Promise.reject(new IamAdminError(refusal, 403)) : Promise.resolve(adminPublishers),
    );
    await open(() => true, { ...listed, publishers: refusing }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    await mounted!.type(field('Policy name'), 'Mine');
    const parent = field('Sub-policy of') as HTMLSelectElement;
    parent.value = 'pol_o';
    parent.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();
    await validated();

    expect(document.querySelector('[data-parent-verdict]')?.textContent).toBe(refusal);
    expect(button('Create policy')?.disabled).toBe(true);
  });

  it('does not take a failure for a refusal: it offers to retry and lets IAM judge the save', async () => {
    let fail = true;
    const flaky = vi.fn((_scope: string, parent?: string | null) =>
      parent && fail ? Promise.reject(new IamAdminError('IAM is not available on this server.', 503)) : Promise.resolve(withinO),
    );
    await open(() => true, { ...listed, publishers: flaky }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    await mounted!.type(field('Policy name'), 'Mine');
    const parent = field('Sub-policy of') as HTMLSelectElement;
    parent.value = 'pol_o';
    parent.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();
    // No builder: the statement editor ("Visual") is open.
    expect(document.querySelector('[role="tab"][aria-selected="true"]')?.textContent).toBe('Visual');
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.type(field('Add to actions of statement 1'), 'nexus:UseFeature');
    await mounted!.click(document.querySelector('[role="option"] button') ?? button('Add statement') ?? null);
    await validated();

    expect(document.querySelector('[data-grantable-failure]')?.textContent).toContain('IAM is not available');
    expect(document.querySelector('[data-parent-verdict]')?.getAttribute('role')).toBe('status');
    expect(button('Create policy')?.disabled).toBe(false);
    fail = false;
    await mounted!.click(button('Retry') ?? null);
    await mounted!.flush();
    expect(document.querySelector('[data-grantable-failure]')).toBeNull();
    // The builder is back, within the parent.
    expect([...document.querySelectorAll('[role="tab"]')].map((t) => t.textContent)).toContain('Builder');
    expect(flaky).toHaveBeenLastCalledWith(WS, 'pol_o', { derive: true });
  });

  it('shows the builder loading, never an empty text view, while a new parent is read', async () => {
    let arrive: (view: PublishersView) => void = () => undefined;
    const slow = vi.fn((_scope: string, parent?: string | null) =>
      parent ? new Promise<PublishersView>((resolve) => (arrive = resolve)) : Promise.resolve(adminPublishers),
    );
    await open(() => true, { ...listed, publishers: slow }, wsScope);
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();
    // Agents chosen, no agent yet: an unfinished choice.
    await mounted!.click(field('Open acme.people Agents'));
    await validated();
    await mounted!.click(field('acme.people Agents: UseAgent'));
    const parent = field('Sub-policy of') as HTMLSelectElement;
    parent.value = 'pol_o';
    parent.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();

    expect(document.querySelector('[data-builder-loading]')).not.toBeNull();
    expect(field('Policy document')).toBeNull();
    arrive(withinO);
    await mounted!.flush();
    expect(document.querySelector('[data-builder-loading]')).toBeNull();
    // Still offered within the parent: kept.
    expect((field('acme.people Agents: UseAgent') as HTMLInputElement).checked).toBe(true);
  });

  it('opens a sub-policy within its parent, and names its parent and sub-policies', async () => {
    const getPolicy = vi.fn((id: string) =>
      Promise.resolve(
        id === 'pol_o'
          ? { ...oAccess, sub_policies: [{ id: 'pol_w', name: 'W analysts', owner_scope: WS, managed: false }] }
          : { ...analysts, parent: { id: 'pol_o', name: 'O access', owner_scope: 'abi:', managed: false }, sub_policies: [] },
      ),
    );
    await open(() => true, { ...listed, publishers, getPolicy }, wsScope);
    await mounted!.click(document.querySelector('[data-policy="pol_w"] button'));
    await mounted!.flush();
    // An existing one is edited within its parent: reading it is enough.
    expect(publishers).toHaveBeenLastCalledWith(WS, 'pol_o', { derive: false });
    expect(field('Parent policy')?.textContent).toContain('Sub-policy of O access');

    await mounted!.click([...document.querySelectorAll('[aria-label="Parent policy"] button')][0]);
    await mounted!.flush();
    expect(field('Sub-policies')?.textContent).toContain('W analysts');
  });

  it('shows IAM’s refusal to delete a parent with sub-policies at its row', async () => {
    const refusal = 'Policy pol_o has sub-policies: pol_w (W analysts). Delete or re-parent them first';
    const deletePolicy = vi.fn().mockRejectedValue(new IamAdminError(refusal, 409));
    await open(() => true, { listPolicies: vi.fn().mockResolvedValue({ items: [{ ...oAccess, owner_scope: WS }, analysts], next_after: null }), deletePolicy }, wsScope);
    await mounted!.click(document.querySelector('[aria-label="Delete O access"]'));
    await mounted!.click(button('Confirm delete') ?? null);
    await mounted!.flush();

    expect(document.querySelector('[data-policy="pol_o"] [data-delete-refusal]')?.textContent).toBe(refusal);
  });
});

describe('PoliciesView, no leak', () => {
  it('offers a user holding only agent A and iam:CreatePolicy only A', async () => {
    const onlyA: PublishersView = {
      scope: WS,
      publishers: [
        { id: 'engine', kind: 'engine', types: [publishedType('iam', 'policy', [['iam:CreatePolicy', ['${scope}/iam:policy/*']]])] },
        {
          id: 'acme.people',
          kind: 'module',
          types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/A']]], { module: 'acme.people' })],
        },
      ],
    };
    const resources = vi.fn((query: ResourceQuery) =>
      Promise.resolve(resourcePage(query.service, query.type, query.module === 'acme.people' ? [['acme.people/A', 'A']] : [])),
    );
    const api = await open((action) => action === 'iam:CreatePolicy', { publishers: vi.fn().mockResolvedValue(onlyA), resources }, wsScope);
    expect(api.listPolicies).not.toHaveBeenCalled();
    await mounted!.click(button('New policy') ?? null);
    await mounted!.flush();

    expect([...document.querySelectorAll('[data-builder-type]')].map((e) => e.getAttribute('data-builder-type'))).toEqual([
      'iam:policy',
      'module:agent@acme.people',
    ]);
    await mounted!.click(field('Open acme.people Agents'));
    await validated();
    expect([...document.querySelectorAll('[data-builder-type="module:agent@acme.people"] input[type="checkbox"]')].map((e) => e.getAttribute('aria-label'))).toEqual([
      'acme.people Agents: UseAgent',
      // The one pattern they may grant is agent A, listed: shown once.
      'acme.people Agents: A',
    ]);

    // The Statements view suggests the same, and nothing else.
    await mounted!.click([...document.querySelectorAll('[role="tab"]')].find((t) => t.textContent === 'Statements') ?? null);
    await mounted!.click(button('Add statement') ?? null);
    const suggestions = () => [...document.querySelectorAll('[role="option"] .access-policy-suggestion-value')].map((e) => e.textContent);
    await mounted!.type(field('Add to actions of statement 1'), ':');
    expect(suggestions()).toEqual(['iam:CreatePolicy', 'module:UseAgent']);
    await mounted!.type(field('Add to actions of statement 1'), 'module:UseAgent');
    await mounted!.click(document.querySelector('[role="option"] button'));
    await mounted!.type(field('Add to resources of statement 1'), '${scope}/module:agent/acme.people/');
    await validated();
    expect(suggestions()).toEqual(['${scope}/module:agent/acme.people/A', '${scope}/module:agent/acme.people/*']);
    expect(resources).toHaveBeenLastCalledWith(expect.objectContaining({ service: 'module', type: 'agent', module: 'acme.people', q: '' }));
  });
});
