// @vitest-environment jsdom
import { createElement, Fragment, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { RequestPreview, activityLogView, statusClass } from './activity-log';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const Show = ({ node }: { node: ReactNode }) => createElement(Fragment, null, node);

const request: ResourceEntry = {
  id: 'user%3Au1/7',
  name: '/api/workspaces',
  kind: 'item',
  actions: ['read', 'download'],
  size: null,
  modified: '2026-10-02T15:04:47+00:00',
  attributes: { method: 'DELETE', status: '503', duration_ms: '2400', summary: '10.0.0.2' },
};

function detailOf(attributes: Record<string, unknown>): ResourceDetail {
  return {
    entry: request,
    content: null,
    view: {
      type: 'json',
      value: {
        actor_id: 'user:u1',
        seq: 7,
        event_type: 'http.request',
        timestamp: '2026-10-02T15:04:47+00:00',
        correlation_id: 'req-9',
        attributes,
      },
    },
  };
}

describe('activity log view', () => {
  it('colors status codes by class', () => {
    expect([200, 304, 404, 503, undefined].map((s) => statusClass(s))).toEqual(['2xx', '3xx', '4xx', '5xx', 'unknown']);
  });

  it('lists requests with method, status, a slow duration and time', async () => {
    const level = activityLogView.level!(1, 'user%3Au1');
    mounted = await mount(Show, { node: level.columns!.map((c) => c.render(request)) });

    expect(level.columns!.map((c) => c.label)).toEqual(['Method', 'Status', 'Took', 'When']);
    expect(mounted.host.querySelector('.data-activity-log-method-delete')?.textContent).toBe('DELETE');
    expect(mounted.host.querySelector('.data-activity-log-status-5xx')?.textContent).toBe('503');
    expect(mounted.host.querySelector('.data-activity-log-slow')?.textContent).toBe('2.4 s');
  });

  it('shows actors with their kind', async () => {
    const actor: ResourceEntry = { ...request, kind: 'container', name: 'Ada', attributes: { kind: 'user' } };
    mounted = await mount(Show, { node: activityLogView.level!(0, '').columns![0].render(actor) });

    expect(mounted.host.textContent).toBe('user');
    expect(activityLogView.nounFor!(actor, 0).one).toBe('actor');
  });

  it('previews a request: line, stats, query, body', async () => {
    mounted = await mount(RequestPreview, {
      detail: detailOf({
        method: 'POST',
        path: '/api/chat',
        status_code: 201,
        duration_ms: 35,
        ip: '10.0.0.2',
        has_auth_header: true,
        query_params: { stream: 'true' },
        request_body: { message: 'hello' },
        content_type: 'application/json',
        custom: 'kept',
      }),
    });
    const text = mounted.host.textContent ?? '';

    expect(mounted.host.querySelector('.data-activity-log-path')?.textContent).toBe('/api/chat?stream=true');
    expect(text).toContain('201');
    expect(text).toContain('35 ms');
    expect(text).toContain('req-9');
    expect(text).toContain('Query parameters');
    expect(text).toContain('message');
    expect(text).toContain('Other attributes');
  });

  it('says why a body was not recorded', async () => {
    mounted = await mount(RequestPreview, {
      detail: detailOf({ method: 'PUT', path: '/api/admin/system/resources/secret/entry', request_body: '[PATH_SKIPPED:42]' }),
    });

    expect(mounted.host.textContent).toContain('not recorded for this path');
    expect(mounted.host.textContent).toContain('42 bytes');
  });
});
