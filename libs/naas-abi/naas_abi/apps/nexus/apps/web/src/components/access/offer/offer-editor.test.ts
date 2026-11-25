// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { OfferApi, OfferState } from '@/lib/access-model/workspace-offer';
import type { ResourceQuery } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessApi } from '@/app/workspace/[workspaceId]/settings/general/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '@/app/workspace/[workspaceId]/settings/general/feature-access-model';
import { WS, fakeApi, publishedType, resourcePage } from '../access-fixtures';
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

  it('lists a module’s items on demand and saves every toggle in one write', async () => {
    const parts = setup();
    await render(parts);
    await mounted!.click(button('Agents of acme.people') ?? null);
    await mounted!.flush();
    expect(parts.api.resources).toHaveBeenCalledWith({ scope: WS, service: 'module', type: 'agent', module: 'acme.people', limit: 200 });
    expect(switchOf('[data-offer-item="acme.people/Coach"]')?.getAttribute('aria-checked')).toBe('true');

    await mounted!.click(switchOf('[data-offer-item="acme.people/Recruiter"]'));
    await mounted!.click(switchOf('[data-offer-item="acme.people/Coach"]'));
    await mounted!.click(switchOf('[data-offer-section="workflows"] [data-offer-module="acme.sales"]'));
    await mounted!.click(switchOf('[data-offer-feature="maps"]'));
    expect(document.body.textContent).toContain('4 unsaved changes');

    await mounted!.click(button('Save offer') ?? null);
    await mounted!.flush();
    expect(parts.offerApi.save).toHaveBeenCalledTimes(1);
    expect(parts.offerApi.save).toHaveBeenCalledWith('ws-1', [
      { kind: 'agents', module: 'acme.people', name: 'Recruiter', offered: true },
      { kind: 'agents', module: 'acme.people', name: 'Coach', offered: false },
      { kind: 'workflows', module: 'acme.sales', name: '*', offered: false },
    ]);
    expect(parts.featureApi.save).toHaveBeenCalledWith('ws-1', [{ feature: 'maps', choice: 'everyone' }]);
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
