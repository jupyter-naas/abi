// @vitest-environment jsdom
import { createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import * as Tooltip from '@radix-ui/react-tooltip';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { MessagePreview, busView, isKvStream } from './bus';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const Show = ({ node }: { node: ReactNode }) =>
  createElement(Tooltip.Provider, null, createElement(Fragment, null, node));

const stream: ResourceEntry = {
  id: 'KV_settings',
  name: 'KV_settings',
  kind: 'container',
  actions: [],
  size: 2048,
  modified: '2026-10-02T15:04:47+00:00',
  attributes: { kind: 'kv', subjects: '$KV.settings.>', messages: '12', consumers: '0', read_only: 'key-value bucket' },
};

const message: ResourceEntry = {
  id: 'naas-abi-events/9',
  name: 'evt.abc.e-1',
  kind: 'item',
  actions: ['read', 'download', 'delete'],
  size: 18,
  modified: '2026-10-02T15:04:47+00:00',
  attributes: { seq: '9', subject: 'evt.abc.e-1', payload: 'json', summary: '{a, b}', 'header:Nats-Auth-Token': '[REDACTED]' },
};

describe('bus view', () => {
  it('shows streams as cards with kind, read-only state, subjects and stats', async () => {
    const level = busView.level!(0, '');
    mounted = await mount(Show, {
      node: [busView.badges!(stream), level.card!(stream), ...level.columns!.map((c) => c.render(stream))],
    });
    const text = mounted.host.textContent ?? '';

    expect(level.layout).toBe('cards');
    expect(text).toContain('KV bucket');
    expect(text).toContain('read-only');
    expect(text).toContain('$KV.settings.>');
    expect(text).toContain('12');
    expect(text).toContain('2.0 KB');
    expect(isKvStream('KV_settings/3') && !isKvStream('ABI_JOBS_zen/3')).toBe(true);
  });

  it('explains why key-value revisions are read-only when the stream is empty', () => {
    expect(busView.level!(1, 'KV_settings').emptyText).toContain('key-value bucket');
    expect(busView.level!(1, 'naas-abi-events').emptyTitle).toBe('No messages stored');
  });

  it('previews a message: envelope, JSON payload, redacted headers', async () => {
    const detail: ResourceDetail = {
      entry: message,
      content: { encoding: 'text', text: '{"a": 1, "b": "two"}', size: 18, truncated: false },
      view: {
        type: 'message',
        subject: 'evt.abc.e-1',
        headers: { 'Nats-Auth-Token': '[REDACTED]', 'X-Trace': 't1' },
        sequence: 9,
        published_at: '2026-10-02T15:04:47+00:00',
      },
    };
    mounted = await mount(MessagePreview, { detail, ctx: {} });
    const text = mounted.host.textContent ?? '';

    expect(mounted.host.querySelector('.data-bus-envelope-subject')?.textContent).toContain('evt.abc.e-1');
    expect(mounted.host.querySelector('.json-tree')?.textContent).toContain('two');
    expect(mounted.host.querySelector('.data-bus-redacted')?.textContent).toBe('[REDACTED]');
    expect(text).toContain('X-Trace');
    expect(text).toContain('Headers · 2');
  });

  it('states what deleting a message does', () => {
    expect(busView.deleteWarning!(message)).toBe(
      'Removes message #9 from naas-abi-events. Consumers that have not read it yet never will, and it cannot be restored.',
    );
    expect(busView.nounFor!(stream, 0).one).toBe('stream');
  });
});
