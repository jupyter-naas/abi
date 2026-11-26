// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { OfferApi, OfferState } from '@/lib/access-model/workspace-offer';
import type { ResourceQuery } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessApi } from '@/app/workspace/[workspaceId]/settings/general/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '@/app/workspace/[workspaceId]/settings/general/feature-access-model';
import { WS, fakeApi, publishedType, resourcePage } from '../access-fixtures';
import { FeatureAccessError } from '@/app/workspace/[workspaceId]/settings/general/feature-access-api';
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
