// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail } from '../data-types';
import { Composer, buildMessage, emailView, parseAddresses } from './email';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const render = async (node: ReactNode) => {
  mounted = await mount(() => createElement('div', null, node), {});
  return mounted.host;
};

const q = (selector: string) => mounted!.host.querySelector(selector);

describe('email view', () => {
  it('parses recipients and builds the API message', () => {
    expect(parseAddresses('a@x.io, nope; b@y.org')).toEqual({ valid: ['a@x.io', 'b@y.org'], invalid: ['nope'] });
    expect(
      JSON.parse(buildMessage({ to: 'a@x.io', cc: '', subject: ' Hi ', text: 'Body', html: '<p>x</p>', withHtml: false })),
    ).toEqual({ to: ['a@x.io'], subject: 'Hi', text: 'Body' });
    expect(
      JSON.parse(buildMessage({ to: 'a@x.io', cc: 'c@x.io', subject: 'Hi', text: '', html: '<p>x</p>', withHtml: true })),
    ).toEqual({ to: ['a@x.io'], cc: ['c@x.io'], subject: 'Hi', text: '', html: '<p>x</p>' });
  });

  it('composes: validates, then sends the message as JSON', async () => {
    const submit = vi.fn(() => Promise.resolve(true));
    mounted = await mount(Composer, { parent: '', busy: false, submit, close: () => {} });
    const send = [...mounted.host.querySelectorAll('button')].find((b) => b.textContent?.includes('Send'))!;

    await mounted.click(send);
    expect(submit).not.toHaveBeenCalled();
    expect(mounted.host.textContent).toContain('Add at least one recipient');

    await mounted.type(q('[aria-label="To"]'), 'ops@example.com, bad');
    await mounted.click(send);
    expect(mounted.host.textContent).toContain('Not an address: bad');

    await mounted.type(q('[aria-label="To"]'), 'ops@example.com');
    await mounted.type(q('[aria-label="Subject"]'), 'Weekly report');
    await mounted.type(q('[aria-label="Message"]'), 'All good.');
    await mounted.click(send);

    expect(submit).toHaveBeenCalledWith('weekly-report', JSON.stringify({ to: ['ops@example.com'], subject: 'Weekly report', text: 'All good.' }));
  });

  it('previews sent mail with its attachments', async () => {
    const detail: ResourceDetail = {
      entry: { id: 'm1', name: 'Hello', kind: 'item', actions: ['read'], size: 900, modified: '2026-10-02T08:00:00Z', attributes: { to: 'ops@example.com' } },
      content: null,
      view: {
        type: 'email',
        from: 'NEXUS <no-reply@x.io>',
        to: ['ops@example.com'],
        subject: 'Hello',
        text: 'Body text',
        attachments: [{ name: 'report.pdf', type: 'application/pdf' }],
      },
    };
    const host = await render(emailView.preview!(detail, {}));

    expect(host.querySelector('.mail-subject')?.textContent).toBe('Hello');
    expect(host.textContent).toContain('Body text');
    expect(host.textContent).toContain('report.pdf');
    expect(emailView.createLabel).toBe('Compose');
    expect(emailView.level!(0, '').emptyText).toContain('only when the adapter keeps a copy');
  });
});
