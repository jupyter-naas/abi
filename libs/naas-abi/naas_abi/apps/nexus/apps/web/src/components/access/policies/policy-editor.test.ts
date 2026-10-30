// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import type { PolicyDocument, PolicyValidation, PublishersView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { WS, catalogsView, fakeApi, managedPolicy, publishedType, publishersOf, readerPolicy, resourcePage, wsScope } from '../access-fixtures';
import { PolicyEditor } from './policy-editor';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const valid = (document: PolicyDocument): PolicyValidation => ({ valid: true, errors: [], document });

const $ = (selector: string) => document.querySelector(selector);
const field = (label: string) => $(`[aria-label="${label}"]`);
const button = (text: string) =>
  [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as HTMLButtonElement | undefined;
const suggestions = () => [...document.querySelectorAll('[role="option"] .access-policy-suggestion-value')].map((e) => e.textContent);

/** An API that validates the document it is given, the way IAM does for a good one. */
function api(over: Record<string, unknown> = {}) {
  return fakeApi({
    validatePolicy: vi.fn((source: { document?: PolicyDocument; text?: string }) => {
      if (source.document) return Promise.resolve(valid(source.document));
      try {
        return Promise.resolve(valid(JSON.parse(source.text ?? '{}')));
      } catch {
        // YAML: the real API reads it; the fake takes it for the reader policy.
        return Promise.resolve(valid(readerPolicy.document));
      }
    }),
    publishers: vi.fn().mockResolvedValue(publishersOf(catalogsView)),
    ...over,
  });
}

const tab = (label: string) => [...document.querySelectorAll('[role="tab"]')].find((t) => t.textContent === label) ?? null;

/** The editor, in the Statements view unless ``builder``: a new policy opens in the builder. */
async function open(props: Partial<Parameters<typeof PolicyEditor>[0]> = {}, { builder = false } = {}) {
  const onSaved = vi.fn();
  const onCancel = vi.fn();
  mounted = await mount(PolicyEditor, {
    api: api(),
    policy: null,
    onSaved,
    onCancel,
    validationDelayMs: 0,
    ...props,
  });
  await mounted.flush();
  const statements = tab('Statements');
  if (!builder && statements?.getAttribute('aria-selected') === 'false') await mounted.click(statements);
  return { onSaved, onCancel };
}

describe('PolicyEditor autocomplete', () => {
  it('suggests actions from the catalogs while typing', async () => {
    await open();
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.type(field('Add to actions of statement 1'), 'triple_store:Q');

    expect(suggestions()[0]).toBe('triple_store:Query');
    expect(document.querySelector('[role="option"]')?.textContent).toContain('read');
    expect(document.querySelector('[role="option"]')?.textContent).toContain('Run a SPARQL query.');
  });

  it('counts what a wildcard action names', async () => {
    await open();
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.type(field('Add to actions of statement 1'), 'triple_store:*');

    expect(document.querySelector('[role="option"]')?.textContent).toContain('matches 4 actions');
  });

  it('suggests resource names one segment at a time, narrowed by the actions', async () => {
    await open();
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.type(field('Add to actions of statement 1'), 'triple_store:Query');
    await mounted!.click(document.querySelector('[role="option"] button'));
    await mounted!.type(field('Add to resources of statement 1'), `${WS}/t`);

    expect(suggestions()).toEqual([`${WS}/triple_store:`]);
    await mounted!.click(document.querySelector('[role="option"] button'));
    expect((field('Add to resources of statement 1') as HTMLInputElement).value).toBe(`${WS}/triple_store:`);
  });
});

describe('PolicyEditor document', () => {
  it('builds the document from the form and saves it through the API', async () => {
    const createPolicy = vi.fn((input) =>
      Promise.resolve({ ...readerPolicy, id: 'pol_new', name: input.name, document: input.document }),
    );
    const { onSaved } = await open({ api: api({ createPolicy }) });
    await mounted!.type(field('Policy name'), 'Graph reader');
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.type(field('Sid of statement 1'), 'Read');
    await mounted!.type(field('Add to actions of statement 1'), 'triple_store:Query');
    await mounted!.click(document.querySelector('[role="option"] button'));
    await mounted!.type(field('Add to resources of statement 1'), `${WS}/triple_store:graph/*`);
    await mounted!.type(field('Add to resources of statement 1'), `${WS}/triple_store:graph/*`);
    field('Add to resources of statement 1')?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await mounted!.flush();
    await mounted!.flush();
    await mounted!.click(button('Create policy') ?? null);
    await mounted!.flush();

    expect(createPolicy).toHaveBeenCalledWith({
      name: 'Graph reader',
      description: '',
      document: {
        version: '2026-10-13',
        statements: [
          {
            sid: 'Read',
            effect: 'Allow',
            actions: ['triple_store:Query'],
            resources: [`${WS}/triple_store:graph/*`],
          },
        ],
      },
    });
    expect(onSaved).toHaveBeenCalled();
  });

  it('changes the effect, moves and removes statements', async () => {
    await open({ policy: { ...readerPolicy, document: { version: '2026-10-13', statements: [
      { effect: 'Allow', actions: ['triple_store:Query'], resources: ['*'] },
      { effect: 'Allow', actions: ['triple_store:Insert'], resources: ['*'] },
    ] } } });
    (field('Effect of statement 2') as HTMLSelectElement).value = 'Deny';
    field('Effect of statement 2')?.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.click(field('Move statement 2 up'));

    expect((field('Effect of statement 1') as HTMLSelectElement).value).toBe('Deny');
    expect(document.querySelector('[aria-label="Actions of statement 1"]')?.textContent).toContain('triple_store:Insert');

    await mounted!.click(field('Remove statement 1'));
    expect(document.querySelectorAll('fieldset')).toHaveLength(1);
  });
});

describe('PolicyEditor validation', () => {
  it('lists every error IAM returns and does not let the policy be saved', async () => {
    const validatePolicy = vi.fn().mockResolvedValue({
      valid: false,
      errors: ['statements[0].actions[0]: unknown action "x:Y"', 'statements[0].resources: must not be empty'],
      document: null,
    });
    const createPolicy = vi.fn();
    await open({ api: api({ validatePolicy, createPolicy }) });
    await mounted!.type(field('Policy name'), 'Bad');
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.flush();

    const errors = $('[aria-label="Validation errors"]');
    expect(errors?.textContent).toContain('unknown action "x:Y"');
    expect(errors?.textContent).toContain('resources: must not be empty');
    expect(button('Create policy')?.disabled).toBe(true);
    expect(createPolicy).not.toHaveBeenCalled();
  });

  it('shows what IAM refused at save, with every error', async () => {
    const updatePolicy = vi.fn().mockRejectedValue(new IamAdminError('Invalid policy document', 422, ['bad one', 'bad two']));
    await open({ api: api({ updatePolicy }), policy: readerPolicy });
    await mounted!.click(button('Save changes') ?? null);
    await mounted!.flush();

    const alert = $('.access-policy-error[role="alert"]');
    expect(alert?.textContent).toContain('Invalid policy document');
    expect(alert?.textContent).toContain('bad one');
    expect(alert?.textContent).toContain('bad two');
    expect(updatePolicy).toHaveBeenCalledWith('pol_1', expect.objectContaining({ expected_revision: 3 }));
  });

  it('offers to reload when someone else changed the policy', async () => {
    const updatePolicy = vi.fn().mockRejectedValue(new IamAdminError('Revision conflict', 409));
    const newer = { ...readerPolicy, name: 'Renamed elsewhere', revision: 4 };
    const getPolicy = vi.fn().mockResolvedValue(newer);
    await open({ api: api({ updatePolicy, getPolicy }), policy: readerPolicy });
    await mounted!.click(button('Save changes') ?? null);
    await mounted!.flush();
    expect(mounted!.host.textContent).toContain('Someone else changed this policy');

    await mounted!.click(button('Reload their version') ?? null);
    await mounted!.flush();
    expect((field('Policy name') as HTMLInputElement).value).toBe('Renamed elsewhere');
    expect(mounted!.host.textContent).not.toContain('Someone else changed this policy');

    await mounted!.click(button('Save changes') ?? null);
    expect(updatePolicy).toHaveBeenLastCalledWith('pol_1', expect.objectContaining({ expected_revision: 4 }));
  });
});

describe('PolicyEditor text view', () => {
  it('round-trips the document through the text view', async () => {
    await open({ policy: readerPolicy });
    await mounted!.click(tab('YAML / JSON'));
    const text = (field('Policy document') as HTMLTextAreaElement).value;
    expect(JSON.parse(text)).toEqual(readerPolicy.document);

    const edited = JSON.stringify({
      version: '2026-10-13',
      statements: [{ effect: 'Deny', actions: ['triple_store:DropGraph'], resources: ['*'] }],
    });
    await mounted!.type(field('Policy document'), edited);
    await mounted!.click(tab('Statements'));
    await mounted!.flush();

    expect((field('Effect of statement 1') as HTMLSelectElement).value).toBe('Deny');
    expect(document.querySelector('[aria-label="Actions of statement 1"]')?.textContent).toContain('triple_store:DropGraph');
  });

  it('keeps a document IAM refuses in the text view, with its errors', async () => {
    const validatePolicy = vi.fn().mockResolvedValue({ valid: false, errors: ['not a policy'], document: null });
    await open({ api: api({ validatePolicy }), policy: readerPolicy });
    await mounted!.click(tab('YAML / JSON'));
    await mounted!.type(field('Policy document'), '{ nope');
    await mounted!.flush();
    await mounted!.click(tab('Statements'));
    await mounted!.flush();

    expect(field('Policy document')).not.toBeNull();
    expect(mounted!.host.textContent).toContain('Fix the errors before leaving the text view');
    expect($('[aria-label="Validation errors"]')?.textContent).toContain('not a policy');
  });

  it('writes YAML on request', async () => {
    await open({ policy: readerPolicy });
    await mounted!.click(tab('YAML / JSON'));
    (field('Text format') as HTMLSelectElement).value = 'yaml';
    field('Text format')?.dispatchEvent(new Event('change', { bubbles: true }));
    await mounted!.flush();

    expect((field('Policy document') as HTMLTextAreaElement).value).toContain('effect: Allow');
  });
});

describe('PolicyEditor sub-policies', () => {
  const subPolicy = {
    ...readerPolicy,
    parent_id: 'pol_parent',
    parent: { id: 'pol_parent', name: 'Org access', owner_scope: 'abi:', managed: false },
  };

  it('shows the parent of a sub-policy and keeps it on save', async () => {
    const updatePolicy = vi.fn((_id: string, input: { name?: string }) => Promise.resolve({ ...subPolicy, ...input }));
    const { onSaved } = await open({ api: api({ updatePolicy }), policy: subPolicy });

    expect(field('Parent policy')?.textContent).toContain('Sub-policy of Org access');
    expect(field('Parent policy')?.textContent).toContain('pol_parent');
    await mounted!.type(field('Policy name'), 'Analysts');
    await mounted!.click(button('Save changes') ?? null);
    await mounted!.flush();

    expect(updatePolicy).toHaveBeenCalledWith('pol_1', expect.objectContaining({ name: 'Analysts', expected_revision: 3 }));
    expect(updatePolicy.mock.calls[0][1]).not.toHaveProperty('parent');
    expect(onSaved).toHaveBeenCalled();
  });

  it('names a parent it could not read by its id, and none for a policy without one', async () => {
    await open({ policy: { ...readerPolicy, parent_id: 'pol_hidden' } });
    expect(field('Parent policy')?.textContent).toContain('Sub-policy of pol_hidden');
    await mounted!.unmount();
    mounted = null;
    await open({ policy: readerPolicy });
    expect(field('Parent policy')).toBeNull();
  });

  it('shows the parent of the newer version after a reload', async () => {
    const updatePolicy = vi.fn().mockRejectedValue(new IamAdminError('Revision conflict', 409));
    const getPolicy = vi.fn().mockResolvedValue({ ...subPolicy, revision: 4, parent_id: null, parent: null });
    await open({ api: api({ updatePolicy, getPolicy }), policy: subPolicy });
    await mounted!.click(button('Save changes') ?? null);
    await mounted!.flush();
    await mounted!.click(button('Reload their version') ?? null);
    await mounted!.flush();

    expect(field('Parent policy')).toBeNull();
  });
});

describe('PolicyEditor read-only', () => {
  it('shows a managed policy without any way to change it', async () => {
    const validatePolicy = vi.fn();
    await open({ api: api({ validatePolicy }), policy: managedPolicy, readOnly: true });

    expect(mounted!.host.textContent).toContain('Managed: IAM writes this policy');
    expect((field('Policy name') as HTMLInputElement).disabled).toBe(true);
    expect(button('Save changes')).toBeUndefined();
    expect(button('Add statement')).toBeUndefined();
    expect(field('Add to actions of statement 1')).toBeNull();
    expect(field('Remove statement 1')).toBeNull();
    expect(document.querySelector('[aria-label="Actions of statement 1"]')?.textContent).toContain('triple_store:Query');
    expect(validatePolicy).not.toHaveBeenCalled();
  });
});

describe('PolicyEditor Statements view listing', () => {
  /** Graphs listed at ws-1; the caller may grant Query on every graph but `secret`. */
  const graphs: PublishersView = {
    scope: WS,
    publishers: [
      {
        id: 'engine',
        kind: 'engine',
        types: [
          {
            ...publishedType('triple_store', 'graph', [['triple_store:Query', ['${scope}/triple_store:graph/*']]]),
            actions: [
              {
                action: 'triple_store:Query',
                name: 'Query',
                level: 'read',
                description: '',
                resources: ['${scope}/triple_store:graph/*'],
                excluded: ['${scope}/triple_store:graph/secret'],
              },
            ],
          },
        ],
      },
    ],
  };
  const resources = vi.fn(() => Promise.resolve(resourcePage('triple_store', 'graph', [['sales', 'Sales'], ['secret', 'Secret']])));

  async function typed(text: string) {
    await open({ api: api({ publishers: vi.fn().mockResolvedValue(graphs), resources }), scope: wsScope });
    await mounted!.click(button('Add statement') ?? null);
    await mounted!.type(field('Add to actions of statement 1'), 'triple_store:Query');
    await mounted!.click(document.querySelector('[role="option"] button'));
    await mounted!.type(field('Add to resources of statement 1'), text);
    await new Promise((resolve) => setTimeout(resolve, 350));
    await mounted!.flush();
  }

  it('suggests what the listing finds that the caller may grant, never what their Deny takes back', async () => {
    await typed('${scope}/triple_store:graph/');
    expect(suggestions()).toContain('${scope}/triple_store:graph/sales');
    expect(suggestions()).not.toContain('${scope}/triple_store:graph/secret');
  });

  it('suggests no wildcard their Deny takes part of back, written at the scope or absolutely', async () => {
    await typed('${scope}/triple_store:graph/');
    expect(suggestions()).not.toContain('${scope}/triple_store:graph/*');
    await mounted!.unmount();
    mounted = null;
    await typed(`${WS}/triple_store:graph/`);
    expect(suggestions()).toContain(`${WS}/triple_store:graph/sales`);
    expect(suggestions()).not.toContain(`${WS}/triple_store:graph/*`);
  });

  it('suggests a listed id only where it is named, not under any base typed', async () => {
    await typed('abi:triple_store:graph/');
    expect(suggestions().filter((s) => s?.endsWith('/sales'))).toEqual([]);
    await mounted!.unmount();
    mounted = null;
    await typed(`\${scope}/nexus:workspace/other/triple_store:graph/`);
    expect(suggestions().filter((s) => s?.endsWith('/sales'))).toEqual([]);
    await mounted!.unmount();
    mounted = null;
    // Named in the scope's container, written absolutely: suggested.
    await typed(`${WS}/triple_store:graph/`);
    expect(suggestions()).toContain(`${WS}/triple_store:graph/sales`);
  });
});
