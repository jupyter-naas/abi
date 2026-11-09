// @vitest-environment jsdom
import { createElement, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PublishersView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { WS, fakeApi, publishedType, resourcePage } from '../../access-fixtures';
import { builderPublishers, type Choices } from './builder-model';
import { PolicyBuilder } from './policy-builder';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const read = (action: string): [string, string[]] => [action, ['${scope}/*']];

/** The engine's types as the API sends them, interleaved; naas_abi's; two modules'. */
const view: PublishersView = {
  scope: WS,
  publishers: [
    {
      id: 'engine',
      kind: 'engine',
      types: [
        publishedType('activity_log', 'actor', [read('activity_log:ListEvents')]),
        publishedType('cache', 'service', [read('cache:Flush')]),
        publishedType('triple_store', 'graph', [read('triple_store:Query'), read('triple_store:DropGraph')]),
        publishedType('cache', 'key', [read('cache:Get')]),
        publishedType('iam', 'policy', [read('iam:CreatePolicy')]),
        publishedType('iam', 'group', [read('iam:CreateGroup')]),
        publishedType('document', 'collection', [read('document:Read')], { container: true }),
        publishedType('document', 'document', [read('document:Write')]),
        publishedType('secret', 'secret', [read('secret:Get')]),
        publishedType('event', 'stream', [read('event:Publish')]),
        publishedType('bus', 'topic', [read('bus:Publish')]),
        publishedType('object_storage', 'object', [read('object_storage:Get')]),
        publishedType('vector_store', 'collection', [read('vector_store:Search')]),
      ],
    },
    {
      id: 'naas_abi',
      kind: 'naas_abi',
      types: [
        publishedType('nexus', 'organization', [read('nexus:GetOrganization')], { container: true }),
        publishedType('nexus', 'workspace', [read('nexus:GetWorkspace')], { container: true }),
        publishedType('nexus', 'feature', [read('nexus:UseFeature')]),
      ],
    },
    {
      id: 'naas_abi_marketplace.ai.chatgpt',
      kind: 'module',
      types: [publishedType('module', 'agent', [read('module:UseAgent')], { module: 'naas_abi_marketplace.ai.chatgpt' })],
    },
    {
      id: 'acme.people',
      kind: 'module',
      types: [publishedType('module', 'agent', [read('module:UseAgent')], { module: 'acme.people' })],
    },
  ],
};
const publishers = builderPublishers(view);
const GRAPH = 'triple_store:graph';

/** The builder with its choices kept by a parent, as the editor keeps them. */
function Harness({ initial }: { initial: Choices }) {
  const [choices, setChoices] = useState<Choices>(initial);
  return createElement(PolicyBuilder, {
    api: fakeApi({
      resources: vi.fn((query: { service: string; type: string }) => Promise.resolve(resourcePage(query.service, query.type, []))),
    }),
    scope: WS,
    validateAt: WS,
    publishers,
    choices,
    onChange: (key: string, choice: Choices[string]) => setChoices((current) => ({ ...current, [key]: choice })),
    kept: 0,
    delayMs: 0,
  });
}

const chosen: Choices = { [GRAPH]: { actions: ['triple_store:Query'], resources: ['${scope}/*'] } };

async function render(initial: Choices = chosen) {
  mounted = await mount(Harness, { initial });
  await mounted.flush();
}

const $ = (selector: string) => document.querySelector(selector);
const field = (label: string) => $(`[aria-label="${label}"]`);
const expanded = (label: string) => field(label)?.getAttribute('aria-expanded');
/** Whether a publisher's types are shown: its body is not hidden. */
const shows = (publisher: string) => !$(`[data-builder-publisher="${publisher}"] > div`)?.hasAttribute('hidden');
const shownPublishers = () => [...document.querySelectorAll('[data-builder-publisher]')].map((e) => e.getAttribute('data-builder-publisher'));
const checked = (label: string) => (field(label) as HTMLInputElement | null)?.checked;

describe('PolicyBuilder: publishers open and close', () => {
  it('opens on load only the publishers with choices, a closed one still counting them', async () => {
    await render();
    expect(shows('engine')).toBe(true);
    expect(shows('naas_abi')).toBe(false);
    expect(expanded('Open naas_abi')).toBe('false');
    expect($('[data-builder-publisher="engine"] [data-builder-count]')?.textContent).toContain('1 of 13 chosen');
    await mounted!.click(field('Close Engine'));
    expect(shows('engine')).toBe(false);
    expect($('[data-builder-publisher="engine"] [data-builder-count]')?.textContent).toContain('1 of 13 chosen');
  });

  it('keeps the choices through closing and opening', async () => {
    await render();
    // A type with a choice opens with its publisher.
    expect(expanded('Close Graphs')).toBe('true');
    expect(checked('Graphs: Query')).toBe(true);
    await mounted!.click(field('Close Engine'));
    await mounted!.click(field('Open Engine'));
    expect(checked('Graphs: Query')).toBe(true);
    expect(checked('Graphs: DropGraph')).toBe(false);
  });
});

describe('PolicyBuilder: the engine by service', () => {
  it('groups the engine’s types by service, the services by name, containers first in each', async () => {
    await render();
    const engine = $('[data-builder-publisher="engine"]')!;
    const services = [...engine.querySelectorAll('[data-builder-service]')].map((e) => e.getAttribute('data-builder-service'));
    expect(services).toEqual([
      'activity_log',
      'bus',
      'cache',
      'document',
      'event',
      'iam',
      'object_storage',
      'secret',
      'triple_store',
      'vector_store',
    ]);
    const typesOf = (service: string) =>
      [...engine.querySelectorAll(`[data-builder-service="${service}"] [data-builder-type]`)].map((e) => e.getAttribute('data-builder-type'));
    expect(typesOf('cache')).toEqual(['cache:key', 'cache:service']);
    expect(typesOf('document')).toEqual(['document:collection', 'document:document']);
    // Only the group holding a choice is open in a large engine; each opens and closes.
    expect(expanded('Close Engine triple_store')).toBe('true');
    expect(expanded('Open Engine cache')).toBe('false');
    await mounted!.click(field('Open Engine cache'));
    expect(expanded('Close Engine cache')).toBe('true');
    // A publisher of one service has no group heading.
    expect($('[data-builder-publisher="naas_abi"] [data-builder-service]')).toBeNull();
    expect(
      [...document.querySelectorAll('[data-builder-publisher="naas_abi"] [data-builder-type]')].map((e) => e.getAttribute('data-builder-type')),
    ).toEqual(['nexus:organization', 'nexus:workspace', 'nexus:feature']);
  });
});

describe('PolicyBuilder: one search', () => {
  const search = (text: string) => mounted!.type(field('Search the builder'), text);

  it('finds a module by its id, opens it and its types, and restores the rest once cleared', async () => {
    await render();
    await search('chatgpt');
    expect(shownPublishers()).toEqual(['naas_abi_marketplace.ai.chatgpt']);
    expect(shows('naas_abi_marketplace.ai.chatgpt')).toBe(true);
    expect(expanded('Close naas_abi_marketplace.ai.chatgpt Agents')).toBe('true');
    await search('');
    expect(shownPublishers()).toEqual(['engine', 'naas_abi', 'acme.people', 'naas_abi_marketplace.ai.chatgpt']);
    expect(shows('naas_abi_marketplace.ai.chatgpt')).toBe(false);
    expect(shows('engine')).toBe(true);
    expect(expanded('Open naas_abi_marketplace.ai.chatgpt Agents')).toBe('false');
  });

  it('finds types by service:type, label and action, across publishers', async () => {
    await render();
    await search('DropGraph');
    expect(shownPublishers()).toEqual(['engine']);
    expect([...document.querySelectorAll('[data-builder-type]')].map((e) => e.getAttribute('data-builder-type'))).toEqual([GRAPH]);
    await search('collection');
    expect([...document.querySelectorAll('[data-builder-type]')].map((e) => e.getAttribute('data-builder-type'))).toEqual([
      'document:collection',
      'vector_store:collection',
    ]);
    await search('agents');
    expect(shownPublishers()).toEqual(['acme.people', 'naas_abi_marketplace.ai.chatgpt']);
  });

  it('keeps what is chosen under a search once it is cleared', async () => {
    await render({});
    await search('acme');
    await mounted!.click(field('acme.people Agents: UseAgent'));
    expect(checked('acme.people Agents: UseAgent')).toBe(true);
    await search('');
    await mounted!.click(field('Open acme.people'));
    await mounted!.click(field('Open acme.people Agents'));
    expect(checked('acme.people Agents: UseAgent')).toBe(true);
    expect($('[data-builder-publisher="acme.people"] [data-builder-count]')?.textContent).toContain('0 of 1 chosen');
  });

  it('says so when nothing matches', async () => {
    await render();
    await search('zzz');
    expect(shownPublishers()).toEqual([]);
    expect($('[data-builder-nothing]')?.textContent).toBe('Nothing matches.');
  });
});
