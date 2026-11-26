// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createOfferApi, type OfferApi, type OfferState, type OntologyRow } from '@/lib/access-model/workspace-offer';
import type { ResourceQuery } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessApi } from '@/app/workspace/[workspaceId]/settings/features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '@/app/workspace/[workspaceId]/settings/features/feature-access-model';
import { WS, fakeApi, publishedType, resourcePage } from '../access-fixtures';
import { FeatureAccessError } from '@/app/workspace/[workspaceId]/settings/features/feature-access-api';
import { WorkspaceOfferEditor } from './offer-editor';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const OFFER: OfferState = {
  workspace_id: 'ws-1',
  scope: WS,
  access_policy: { id: 'pol_w', name: 'Sales access', owner_scope: WS },
  editable: true,
  whole_module: '*',
  offered: {
    agents: [{ module: 'acme.people', name: 'Coach' }],
    apps: [],
    workflows: [{ module: 'acme.sales', name: '*' }],
    pipelines: [],
  },
};

function feature(over: Partial<FeatureRow> & Pick<FeatureRow, 'key' | 'label'>): FeatureRow {
  return {
    choice: 'nobody',
    principals: [],
    policy: null,
    hand_edited: false,
    offered: true,
    held: true,
    editable: true,
    reason: null,
    also: [],
    ...over,
  };
}

const FEATURES: FeatureAccessState = {
  workspace_id: 'ws-1',
  scope: WS,
  access_policy: OFFER.access_policy,
  members_group: null,
  can: { create: true, attach: true, detach: true, widen: true },
  features: [
    feature({ key: 'chat', label: 'Chat', choice: 'everyone' }),
    feature({ key: 'maps', label: 'Maps' }),
    feature({ key: 'graph', label: 'Graph', offered: false }),
  ],
};

const PUBLISHERS = {
  scope: WS,
  publishers: [
    {
      id: 'acme.people',
      kind: 'module' as const,
      types: [publishedType('module', 'agent', [['module:UseAgent', ['${scope}/module:agent/acme.people/*']]], { module: 'acme.people' })],
    },
    {
      id: 'acme.sales',
      kind: 'module' as const,
      types: [
        publishedType('module', 'workflow', [['module:RunWorkflow', ['${scope}/module:workflow/acme.sales/*']]], { module: 'acme.sales' }),
      ],
    },
  ],
};

function setup(offer: OfferState = OFFER) {
  const offerApi = { read: vi.fn().mockResolvedValue(offer), save: vi.fn().mockResolvedValue(offer) };
  const featureApi = { read: vi.fn().mockResolvedValue(FEATURES), save: vi.fn().mockResolvedValue(FEATURES) };
  const api = fakeApi({
    publishers: vi.fn().mockResolvedValue(PUBLISHERS),
    resources: vi.fn((query: ResourceQuery) =>
      Promise.resolve(
        resourcePage('module', query.type, [
          ['acme.people/Coach', 'Coach'],
          ['acme.people/Recruiter', 'Recruiter'],
        ]),
      ),
    ),
  });
  return { offerApi, featureApi, api };
}

async function render(parts: ReturnType<typeof setup>) {
  mounted = await mount(WorkspaceOfferEditor, {
    workspaceId: 'ws-1',
    scope: WS,
    workspaceName: 'Sales',
    api: parts.api,
    offerApi: parts.offerApi as unknown as OfferApi,
    featureApi: parts.featureApi as unknown as FeatureAccessApi,
  });
  await mounted.flush();
  return mounted;
}

const switchOf = (selector: string) => document.querySelector(`${selector} [role="switch"]`) as HTMLButtonElement | null;
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(text)) as HTMLButtonElement | undefined;

describe('WorkspaceOfferEditor', () => {
  it('shows the features and each kind by module as toggles, not JSON', async () => {
    await render(setup());
    expect(document.body.textContent).toContain('Everyone in Sales workspace reaches what is on here');
    expect(switchOf('[data-offer-feature="chat"]')?.getAttribute('aria-checked')).toBe('true');
    expect(switchOf('[data-offer-feature="maps"]')?.getAttribute('aria-checked')).toBe('false');
    // Not offered by the organization: cannot be turned on.
    expect(switchOf('[data-offer-feature="graph"]')?.disabled).toBe(true);
    expect(switchOf('[data-offer-section="agents"] [data-offer-module="acme.people"]')?.getAttribute('aria-checked')).toBe('false');
    expect(switchOf('[data-offer-section="workflows"] [data-offer-module="acme.sales"]')?.getAttribute('aria-checked')).toBe('true');
    expect(document.querySelector('[data-offer-section="apps"]')?.textContent).toContain('No module has apps');
    expect(document.querySelector('textarea')).toBeNull();
  });

  it('shows the offer as soon as it is read, the features following', async () => {
    const parts = setup();
    let answer: (state: FeatureAccessState) => void = () => undefined;
    parts.featureApi.read = vi.fn(() => new Promise<FeatureAccessState>((resolve) => (answer = resolve)));
    await render(parts);
    expect(document.body.textContent).toContain('Everyone in Sales workspace reaches what is on here');
    expect(document.querySelector('[data-offer-section="features"]')?.textContent).toContain('Loading the features');
    answer(FEATURES);
    await mounted!.flush();
    expect(switchOf('[data-offer-feature="chat"]')?.getAttribute('aria-checked')).toBe('true');
  });

  it('tells a refusal from a failure: a failure is said as one, with Retry', async () => {
    const parts = setup();
    parts.featureApi.read = vi.fn().mockRejectedValueOnce(new FeatureAccessError('Service Unavailable', 503)).mockResolvedValue(FEATURES);
    await render(parts);
    const features = () => document.querySelector('[data-offer-section="features"]')?.textContent ?? '';
    expect(features()).not.toContain('You may not read');
    expect(features()).toContain('could not be read');
    await mounted!.click(button('Retry'));
    await mounted!.flush();
    expect(switchOf('[data-offer-feature="chat"]')?.getAttribute('aria-checked')).toBe('true');

    await mounted!.unmount();
    const refused = setup();
    refused.featureApi.read = vi.fn().mockRejectedValue(new FeatureAccessError('Forbidden', 403));
    await render(refused);
    expect(features()).toContain('You may not read the features of this workspace.');
    expect(button('Retry')).toBeUndefined();
  });

  it('lists a module’s items on demand and saves each toggle at once', async () => {
    const parts = setup();
    const onChanged = vi.fn();
    mounted = await mount(WorkspaceOfferEditor, {
      workspaceId: 'ws-1',
      scope: WS,
      workspaceName: 'Sales',
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      featureApi: parts.featureApi as unknown as FeatureAccessApi,
      onChanged,
    });
    await mounted.flush();
    await mounted.click(button('Agents of acme.people') ?? null);
    await mounted.flush();
    expect(parts.api.resources).toHaveBeenCalledWith({ scope: WS, service: 'module', type: 'agent', module: 'acme.people', limit: 200 });
    expect(switchOf('[data-offer-item="acme.people/Coach"]')?.getAttribute('aria-checked')).toBe('true');

    await mounted.click(switchOf('[data-offer-item="acme.people/Recruiter"]'));
    await mounted.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith('ws-1', [
      { kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true },
    ]);
    expect(document.querySelector('[data-offer-notice]')?.textContent).toBe('Recruiter added to the offer.');

    await mounted.click(switchOf('[data-offer-section="workflows"] [data-offer-module="acme.sales"]'));
    await mounted.flush();
    expect(parts.offerApi.save).toHaveBeenLastCalledWith('ws-1', [
      { kind: 'workflows', module: 'acme.sales', name: '*', offered: false },
    ]);

    await mounted.click(switchOf('[data-offer-feature="maps"]'));
    await mounted.flush();
    expect(parts.featureApi.save).toHaveBeenCalledWith('ws-1', [{ feature: 'maps', choice: 'everyone' }]);
    expect(document.querySelector('[data-offer-notice]')?.textContent).toBe('Maps added to the offer.');
    // Each save tells the page: "<W> access" has a new revision. No Save button is left.
    expect(onChanged).toHaveBeenCalledTimes(3);
    expect(button('Save offer')).toBeUndefined();
  });

  it('says a refusal of a feature at its row, and tells nothing changed', async () => {
    const parts = setup();
    parts.featureApi.save = vi.fn().mockResolvedValue({ ...FEATURES, errors: { maps: 'Not offered by the organization' } });
    const onChanged = vi.fn();
    mounted = await mount(WorkspaceOfferEditor, {
      workspaceId: 'ws-1',
      scope: WS,
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      featureApi: parts.featureApi as unknown as FeatureAccessApi,
      onChanged,
    });
    await mounted.flush();
    await mounted.click(switchOf('[data-offer-feature="maps"]'));
    await mounted.flush();
    expect(document.querySelector('[data-offer-feature="maps"]')?.textContent).toContain('Not offered by the organization');
    expect(document.querySelector('[data-offer-notice]')).toBeNull();
    expect(onChanged).not.toHaveBeenCalled();
  });

  it('an item is on with its whole module, and cannot be turned off alone', async () => {
    const whole = { ...OFFER, offered: { ...OFFER.offered, agents: [{ module: 'acme.people', name: '*' }] } };
    await render(setup(whole));
    await mounted!.click(button('Agents of acme.people') ?? null);
    await mounted!.flush();
    const recruiter = switchOf('[data-offer-item="acme.people/Recruiter"]');
    expect(recruiter?.getAttribute('aria-checked')).toBe('true');
    expect(recruiter?.disabled).toBe(true);
  });

  it('is read-only when IAM does not let the caller change "<W> access"', async () => {
    await render(setup({ ...OFFER, editable: false }));
    expect(document.querySelector('[data-offer-readonly]')?.textContent).toContain('IAM does not let you change Sales access');
    expect(switchOf('[data-offer-section="agents"] [data-offer-module="acme.people"]')?.disabled).toBe(true);
  });

  it('shows nothing on another policy’s page', async () => {
    const parts = setup();
    mounted = await mount(WorkspaceOfferEditor, {
      workspaceId: 'ws-1',
      scope: WS,
      policyId: 'pol_other',
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      featureApi: parts.featureApi as unknown as FeatureAccessApi,
    });
    await mounted.flush();
    expect(document.querySelector('[aria-label="Workspace offer"]')).toBeNull();
  });
});

describe('WorkspaceOfferEditor: search sources', () => {
  const withSources = (sources: string[]): OfferState => ({
    ...OFFER,
    offered: { ...OFFER.offered, search_sources: sources },
  });

  it('shows each source of the search as a toggle and saves it in the offer', async () => {
    const parts = setup(withSources(['chat', 'web.wikipedia']));
    const saveSearchSources = vi.fn().mockResolvedValue(withSources(['chat']));
    Object.assign(parts.offerApi, { saveSearchSources });
    await render(parts);
    const section = document.querySelector('[data-offer-section="search-sources"]');
    expect(section?.textContent).toContain('Search sources');
    expect(switchOf('[data-offer-source="chat"]')?.getAttribute('aria-checked')).toBe('true');
    expect(switchOf('[data-offer-source="files"]')?.getAttribute('aria-checked')).toBe('false');
    expect(switchOf('[data-offer-source="web.wikipedia"]')?.getAttribute('aria-checked')).toBe('true');
    expect(document.querySelector('[data-offer-source="web.wikipedia"]')?.textContent).toContain('Wikipedia');
    await mounted!.click(switchOf('[data-offer-source="web.wikipedia"]'));
    await mounted!.flush();
    expect(saveSearchSources).toHaveBeenCalledWith('ws-1', { 'web.wikipedia': false });
    expect(switchOf('[data-offer-source="web.wikipedia"]')?.getAttribute('aria-checked')).toBe('false');
    expect(document.body.textContent).toContain('Wikipedia removed from the offer');
  });

  it('keeps the sources read-only where IAM does not let the caller change the offer', async () => {
    await render(setup({ ...withSources(['chat']), editable: false }));
    expect(switchOf('[data-offer-source="chat"]')?.disabled).toBe(true);
  });
});

describe('WorkspaceOfferEditor: files', () => {
  const FILES: OfferState = {
    ...OFFER,
    files: [
      {
        key: 'org_files',
        label: 'Organization Files',
        mode: 'read',
        modes: ['off', 'read', 'write'],
        choices: ['off', 'read', 'write'],
        editable: true,
        reason: null,
      },
      {
        key: 'platform_files',
        label: 'Platform Files',
        mode: 'write',
        modes: ['off', 'read', 'write'],
        choices: ['off', 'read', 'write'],
        editable: true,
        reason: null,
      },
      {
        key: 'system_files',
        label: 'System Files',
        mode: 'off',
        modes: ['off', 'read'],
        choices: ['off'],
        editable: false,
        reason: 'Only a platform admin gives System Files.',
      },
    ],
    my_files: { members: 'write', viewers: 'read' },
  };
  const select = (key: string) => document.querySelector(`[data-offer-file="${key}"] select`) as HTMLSelectElement | null;
  const withFilesFeature = (parts: ReturnType<typeof setup>) => {
    const features = { ...FEATURES, features: [...FEATURES.features, feature({ key: 'files', label: 'Files', choice: 'everyone' })] };
    parts.featureApi.read = vi.fn().mockResolvedValue(features);
    return parts;
  };

  it('shows Workspace Files as the files feature, the files given outside as modes, and My Files', async () => {
    await render(withFilesFeature(setup(FILES)));
    const section = document.querySelector('[data-offer-section="files"]');
    expect(section?.textContent).toContain('Workspace Files');
    // The files feature is shown here, not among the features.
    expect(section?.querySelector('[data-offer-feature="files"] [role="switch"]')?.getAttribute('aria-checked')).toBe('true');
    expect(document.querySelectorAll('[data-offer-feature="files"]').length).toBe(1);
    expect(select('org_files')?.value).toBe('read');
    expect(select('platform_files')?.value).toBe('write');
    expect([...(select('system_files')?.options ?? [])].map((o) => o.textContent)).toEqual(['Off', 'Read']);
    expect(select('system_files')?.disabled).toBe(true);
    expect(document.querySelector('[data-offer-file="system_files"]')?.textContent).toContain('Only a platform admin gives System Files.');
    expect(document.querySelector('[data-offer-my-files]')?.textContent).toBe(
      'My Files: every Member writes theirs; Viewers read theirs (a setting of the deployment).',
    );
  });

  it('saves a mode in the offer at once, and offers only the modes the caller may choose', async () => {
    const narrowed: OfferState = {
      ...FILES,
      files: FILES.files!.map((row) => (row.key === 'platform_files' ? { ...row, mode: 'read', choices: ['off', 'read'] } : row)),
    };
    const parts = setup(FILES);
    const saveFiles = vi.fn().mockResolvedValue(narrowed);
    Object.assign(parts.offerApi, { saveFiles });
    await render(parts);
    await mounted!.select(select('platform_files'), 'read');
    await mounted!.flush();
    expect(saveFiles).toHaveBeenCalledWith('ws-1', { platform_files: 'read' });
    expect(select('platform_files')?.value).toBe('read');
    expect(document.querySelector('[data-offer-notice]')?.textContent).toBe('Platform Files: Read.');
    const write = [...(select('platform_files')?.options ?? [])].find((o) => o.value === 'write');
    expect(write?.disabled).toBe(true);
  });

  it('says when Viewers have no My Files, and shows no Organization Files row where the API gives none', async () => {
    await render(setup({ ...FILES, files: FILES.files!.filter((r) => r.key !== 'org_files'), my_files: { members: 'write', viewers: 'none' } }));
    expect(select('org_files')).toBeNull();
    expect(document.querySelector('[data-offer-my-files]')?.textContent).toContain('Viewers have none');
  });
});

describe('WorkspaceOfferEditor: graphs', () => {
  it('shows the Graphs part as a summary, changed in Settings › Graphs', async () => {
    const graphs = { read: 3, write: 1, read_all: true, include_owned: false, allow_create: false };
    await render(setup({ ...OFFER, graphs }));
    const section = document.querySelector('[data-offer-section="graphs"]');
    expect([...(section?.querySelectorAll('[data-offer-graphs] li') ?? [])].map((li) => li.textContent)).toEqual([
      '3 graphs given to read, 1 of them to write.',
      'Every graph of its organization is read, the ones made later too.',
      'Its own graphs are excluded.',
      'Creating graphs is closed.',
    ]);
    // Read only here: no toggle, a link to where it is changed.
    expect(section?.querySelector('[role="switch"], select')).toBeNull();
    expect(section?.querySelector('a')?.getAttribute('href')).toBe('/workspace/ws-1/settings/graphs');
  });

  it('says when nothing is given, and shows no section for an offer that does not say', async () => {
    const graphs = { read: 0, write: 0, read_all: false, include_owned: true, allow_create: true };
    await render(setup({ ...OFFER, graphs }));
    expect(document.querySelector('[data-offer-graphs]')?.textContent).toBe(
      'No graph of another workspace or of the platform is given.',
    );
    await mounted?.unmount();
    mounted = null;
    await render(setup());
    expect(document.querySelector('[data-offer-section="graphs"]')).toBeNull();
  });
});

describe('WorkspaceOfferEditor: models', () => {
  const withModels = (offered: string[], defaultModel: string | null, available = ['gpt-x', 'qwen-3.8']): OfferState => ({
    ...OFFER,
    models: { offered, default: defaultModel, every: offered.includes('*'), available },
  });

  it('shows every model as one switch, and limits the workspace to one model as its default', async () => {
    const parts = setup(withModels(['*'], null));
    const saveModels = vi.fn().mockResolvedValue(withModels(['gpt-x'], 'gpt-x'));
    Object.assign(parts.offerApi, { saveModels });
    await render(parts);
    const section = document.querySelector('[data-offer-section="models"]');
    expect(section?.textContent).toContain('Models');
    expect(switchOf('[data-offer-models-every]')?.getAttribute('aria-checked')).toBe('true');
    expect(document.querySelector('[data-offer-model="gpt-x"]')).toBeNull();
    await mounted!.click(switchOf('[data-offer-models-every]'));
    await mounted!.flush();
    expect(saveModels).toHaveBeenCalledWith('ws-1', ['gpt-x'], 'gpt-x');
    expect(switchOf('[data-offer-model="gpt-x"]')?.getAttribute('aria-checked')).toBe('true');
    expect(switchOf('[data-offer-model="qwen-3.8"]')?.getAttribute('aria-checked')).toBe('false');
  });

  it('adds and removes a model, keeps a default among them, and goes back to every model', async () => {
    const parts = setup(withModels(['gpt-x', 'qwen-3.8'], 'qwen-3.8'));
    const saveModels = vi.fn().mockResolvedValue(withModels(['gpt-x'], 'gpt-x'));
    Object.assign(parts.offerApi, { saveModels });
    await render(parts);
    const select = document.querySelector('[data-offer-models-default] select') as HTMLSelectElement;
    expect(select.value).toBe('qwen-3.8');
    expect([...select.options].map((o) => o.value)).toEqual(['gpt-x', 'qwen-3.8']);
    // Removing the default makes another offered model the default.
    await mounted!.click(switchOf('[data-offer-model="qwen-3.8"]'));
    await mounted!.flush();
    expect(saveModels).toHaveBeenLastCalledWith('ws-1', ['gpt-x'], 'gpt-x');
    // The last model cannot be removed: the switch to every model does it.
    expect(switchOf('[data-offer-model="gpt-x"]')?.disabled).toBe(true);
    saveModels.mockResolvedValue(withModels(['*'], null));
    await mounted!.click(switchOf('[data-offer-models-every]'));
    await mounted!.flush();
    expect(saveModels).toHaveBeenLastCalledWith('ws-1', ['*'], null);
  });

  it('is read-only where IAM does not let the caller change the offer, and absent where the API says nothing', async () => {
    await render(setup({ ...withModels(['qwen-3.8'], 'qwen-3.8'), editable: false }));
    expect(switchOf('[data-offer-models-every]')?.disabled).toBe(true);
    expect(switchOf('[data-offer-model="qwen-3.8"]')?.disabled).toBe(true);
    await mounted!.unmount();
    mounted = null;
    await render(setup(OFFER));
    expect(document.querySelector('[data-offer-section="models"]')).toBeNull();
  });
});

describe('WorkspaceOfferEditor: maps', () => {
  it('shows the Maps part as a summary, changed in Settings › Maps', async () => {
    const maps = {
      feeds: { every: true, named: 0, closed: 2, shared: 1 },
      basemaps: { every: false, named: 3, closed: 0, shared: 0 },
    };
    await render(setup({ ...OFFER, maps }));
    const section = document.querySelector('[data-offer-section="maps"]');
    expect([...(section?.querySelectorAll('[data-offer-maps] li') ?? [])].map((li) => li.textContent)).toEqual([
      'Every map feed of the platform, the ones added later too.',
      '2 map feeds of the platform not used here.',
      '1 map feed shared by other workspaces.',
      '3 basemaps of the platform.',
    ]);
    // Read only here: no toggle, a link to where it is changed.
    expect(section?.querySelector('[role="switch"], select')).toBeNull();
    expect(section?.querySelector('a')?.getAttribute('href')).toBe('/workspace/ws-1/settings/maps');
  });

  it('says when nothing is given, and shows no section for an offer that does not say', async () => {
    const none = { every: false, named: 0, closed: 0, shared: 0 };
    await render(setup({ ...OFFER, maps: { feeds: none, basemaps: none } }));
    expect([...document.querySelectorAll('[data-offer-maps] li')].map((li) => li.textContent)).toEqual([
      'No map feed of the platform.',
      'No basemap of the platform.',
    ]);
    await mounted?.unmount();
    mounted = null;
    await render(setup());
    expect(document.querySelector('[data-offer-section="maps"]')).toBeNull();
  });
});

describe('WorkspaceOfferEditor: ontologies', () => {
  const row = (over: Partial<OntologyRow> & Pick<OntologyRow, 'id' | 'label'>): OntologyRow => ({
    module: 'core',
    offered: false,
    available: true,
    assignable: true,
    editable: true,
    reason: null,
    ...over,
  });
  const ONTOLOGIES: OfferState = {
    ...OFFER,
    ontologies: {
      offered: ['Core:BFO.ttl', 'gone:Old.ttl'],
      error: null,
      rows: [
        row({ id: 'core:agent.ttl', label: 'Agent' }),
        row({ id: 'core:bfo.ttl', label: 'BFO core', offered: true }),
        row({ id: 'gone:Old.ttl', label: 'gone:Old.ttl', module: null, offered: true, available: false, assignable: false }),
        row({
          id: 'acme.sales:sales.ttl',
          label: 'Sales',
          module: 'acme.sales',
          assignable: false,
          editable: false,
          reason: 'Not yours to assign: an administrator of its organization may (nexus:AssignOntology).',
        }),
      ],
    },
  };
  const ontologySwitch = (id: string) => switchOf(`[data-offer-ontology="${id}"]`);

  it('shows each ontology file as a toggle: offered, read-only with its reason, or out of the catalog', async () => {
    await render(setup(ONTOLOGIES));
    const section = document.querySelector('[data-offer-section="ontologies"]');
    expect(section?.querySelector('h4')?.textContent).toBe('Ontologies');
    expect(ontologySwitch('core:bfo.ttl')?.getAttribute('aria-checked')).toBe('true');
    expect(ontologySwitch('core:agent.ttl')?.getAttribute('aria-checked')).toBe('false');
    expect(ontologySwitch('core:agent.ttl')?.disabled).toBe(false);
    expect(document.querySelector('[data-offer-ontology="core:agent.ttl"]')?.textContent).toContain('core');
    // What the caller may not give: read-only, saying who gives it.
    expect(ontologySwitch('acme.sales:sales.ttl')?.disabled).toBe(true);
    expect(document.querySelector('[data-offer-ontology="acme.sales:sales.ttl"]')?.textContent).toContain(
      'an administrator of its organization may (nexus:AssignOntology)',
    );
    // A ref no file answers to: on, and removable.
    expect(document.querySelector('[data-offer-ontology="gone:Old.ttl"]')?.textContent).toContain(
      'Unavailable in the current catalog',
    );
    expect(ontologySwitch('gone:Old.ttl')?.getAttribute('aria-checked')).toBe('true');
    expect(ontologySwitch('gone:Old.ttl')?.disabled).toBe(false);
  });

  it('saves each toggle in the offer at once, by the file’s id', async () => {
    const after: OfferState = {
      ...ONTOLOGIES,
      ontologies: {
        ...ONTOLOGIES.ontologies!,
        offered: [...ONTOLOGIES.ontologies!.offered, 'core:agent.ttl'],
        rows: ONTOLOGIES.ontologies!.rows.map((r) => (r.id === 'core:agent.ttl' ? { ...r, offered: true } : r)),
      },
    };
    const parts = setup(ONTOLOGIES);
    const saveOntologies = vi.fn().mockResolvedValue(after);
    Object.assign(parts.offerApi, { saveOntologies });
    const onChanged = vi.fn();
    mounted = await mount(WorkspaceOfferEditor, {
      workspaceId: 'ws-1',
      scope: WS,
      workspaceName: 'Sales',
      api: parts.api,
      offerApi: parts.offerApi as unknown as OfferApi,
      featureApi: parts.featureApi as unknown as FeatureAccessApi,
      onChanged,
    });
    await mounted.flush();
    await mounted.click(ontologySwitch('core:agent.ttl'));
    await mounted.flush();
    expect(saveOntologies).toHaveBeenCalledWith('ws-1', { 'core:agent.ttl': true });
    expect(ontologySwitch('core:agent.ttl')?.getAttribute('aria-checked')).toBe('true');
    expect(document.querySelector('[data-offer-notice]')?.textContent).toBe('Agent added to the offer.');
    expect(onChanged).toHaveBeenCalledTimes(1);

    await mounted.click(ontologySwitch('gone:Old.ttl'));
    await mounted.flush();
    expect(saveOntologies).toHaveBeenLastCalledWith('ws-1', { 'gone:Old.ttl': false });
  });

  it('says a refusal and keeps the switch as it was', async () => {
    const parts = setup(ONTOLOGIES);
    const saveOntologies = vi.fn().mockRejectedValue(new Error('You may not assign core:agent.ttl to this workspace'));
    Object.assign(parts.offerApi, { saveOntologies });
    await render(parts);
    await mounted!.click(ontologySwitch('core:agent.ttl'));
    await mounted!.flush();
    expect(document.querySelector('.access-policy-error[role="alert"]')?.textContent).toContain('You may not assign core:agent.ttl');
    expect(ontologySwitch('core:agent.ttl')?.getAttribute('aria-checked')).toBe('false');
    expect(document.querySelector('[data-offer-notice]')).toBeNull();
  });

  it('is read-only where IAM does not let the caller change "<W> access"', async () => {
    const readOnly = {
      ...ONTOLOGIES,
      editable: false,
      ontologies: {
        ...ONTOLOGIES.ontologies!,
        rows: ONTOLOGIES.ontologies!.rows.map((r) => ({ ...r, editable: false, reason: 'IAM does not let you change Sales access.' })),
      },
    };
    await render(setup(readOnly));
    for (const id of ['core:agent.ttl', 'core:bfo.ttl', 'gone:Old.ttl']) expect(ontologySwitch(id)?.disabled).toBe(true);
  });

  it('says when the files could not be listed, and shows no section where the deployment has none', async () => {
    await render(setup({ ...OFFER, ontologies: { offered: ['core:bfo.ttl'], rows: [], error: 'The ontology files could not be listed.' } }));
    expect(document.querySelector('[data-offer-section="ontologies"]')?.textContent).toContain(
      'The ontology files could not be listed.',
    );
    await mounted?.unmount();
    mounted = null;
    await render(setup({ ...OFFER, ontologies: null }));
    expect(document.querySelector('[data-offer-section="ontologies"]')).toBeNull();
  });

  it('writes a change with PUT /offer/ontologies', async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(ONTOLOGIES), { status: 200 }));
    const state = await createOfferApi(fetcher).saveOntologies('ws 1', { 'core:bfo.ttl': false });
    expect(fetcher).toHaveBeenCalledWith('/api/workspaces/ws%201/offer/ontologies', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ changes: { 'core:bfo.ttl': false } }),
    });
    expect(state.ontologies?.offered).toEqual(['Core:BFO.ttl', 'gone:Old.ttl']);
    const refused = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'You may not assign x' }), { status: 403 }));
    await expect(createOfferApi(refused).saveOntologies('ws-1', { x: true })).rejects.toMatchObject({
      status: 403,
      message: 'You may not assign x',
    });
  });
});
