// @vitest-environment jsdom
import { createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { EventPreview, Facets, domainIcon, eventView, humanize } from './event';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const Show = ({ node }: { node: ReactNode }) => createElement(Fragment, null, node);

const event: ResourceEntry = {
  id: 'http%3A%2F%2Fx%2FKeyValueSet/42',
  name: '#42',
  kind: 'item',
  actions: ['read', 'download'],
  size: 812,
  modified: '2026-10-02T15:04:47+00:00',
  attributes: {
    seq: '42',
    type: 'http://ontology.naas.ai/abi/keyvalue/KeyValueSet',
    domain: 'keyvalue',
    actor: 'user-2ab',
    via: 'api',
    summary: 'key=session:42 · size=12 B',
  },
};

describe('event view', () => {
  it('names types in words and picks domain icons', () => {
    expect(humanize('AgentAIMessageEmitted')).toBe('Agent AI message emitted');
    expect(humanize('CreateUser')).toBe('Create user');
    expect(domainIcon('keyvalue')).not.toBe(domainIcon('unknown-domain'));
  });

  it('renders summaries as key=value facets', async () => {
    mounted = await mount(Facets, { text: 'key=session:42 · size=12 B · plain' });
    const facets = [...mounted.host.querySelectorAll('.data-event-facet')].map((f) => f.textContent);

    expect(facets).toEqual(['keysession:42', 'size12 B', 'plain']);
    expect(mounted.host.querySelector('.data-event-facet-key')?.textContent).toBe('key');
  });

  it('lists types with domain, count and last seen, and events with time, actor and via', async () => {
    const types = eventView.level!(0, '');
    const events = eventView.level!(1, 'x');
    const type: ResourceEntry = { ...event, kind: 'container', attributes: { domain: 'agent', count: '5368' } };

    mounted = await mount(Show, {
      node: [...types.columns!.map((c) => c.render(type)), ...events.columns!.map((c) => c.render(event))],
    });

    expect(types.columns!.map((c) => c.label)).toEqual(['Domain', 'Events', 'Last seen']);
    expect(events.columns!.map((c) => c.label)).toEqual(['When', 'Actor', 'Size']);
    expect(mounted.host.textContent).toContain('agent');
    expect(mounted.host.textContent).toContain('5,368');
    expect(mounted.host.textContent).toContain('user-2ab');
    expect(mounted.host.textContent).toContain('812 B');
    expect(eventView.nounFor!(type, 0).one).toBe('event type');
  });

  it('shows how long ago, then the clock time', async () => {
    const level = eventView.level!(1, 'x');
    mounted = await mount(Show, { node: [level.columns![0].render(event), eventView.badges!(event)] });

    expect(mounted.host.querySelector('.data-event-time-exact')?.textContent).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(mounted.host.textContent).toContain('api');
  });

  it('previews the informative fields first, then the whole payload', async () => {
    const detail: ResourceDetail = {
      entry: event,
      content: { encoding: 'text', text: '{}', size: 2, truncated: false },
      view: {
        type: 'json',
        value: {
          _uri: 'http://ontology.naas.ai/abi/1',
          key: 'session:42',
          graph_name: 'http://ontology.naas.ai/graph/nexus-identity',
          changes_json: '{"enabled_override": {"from": null, "to": true}}',
          created_at: '2026-10-02T15:04:47+00:00',
        },
      },
    };
    mounted = await mount(EventPreview, { detail });
    const fields = [...mounted.host.querySelectorAll('.data-event-field dt')].map((d) => d.textContent);

    expect(fields).toEqual(['key', 'graph name', 'changes json']);
    expect(mounted.host.querySelector('.data-event-iri')?.textContent).toBe('http://ontology.naas.ai/graph/nexus-identity');
    expect(mounted.host.textContent).toContain('enabled_override');
    expect(mounted.host.textContent).toContain('Payload');
  });
});
