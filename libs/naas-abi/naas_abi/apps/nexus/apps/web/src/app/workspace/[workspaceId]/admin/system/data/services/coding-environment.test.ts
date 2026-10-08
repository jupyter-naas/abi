// @vitest-environment jsdom
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { codingEnvironmentView } from './coding-environment';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const render = async (node: ReactNode) => {
  mounted = await mount(() => createElement('div', null, node), {});
  return mounted.host;
};

const environment: ResourceEntry = {
  id: 'environments/ws-1',
  name: 'research',
  kind: 'item',
  actions: ['read', 'delete'],
  size: null,
  modified: '2026-10-01T10:00:00Z',
  attributes: { phase: 'running', ready: 'yes', owner: 'ada@example.com', template: 'docker' },
};

describe('coding environment view', () => {
  it('shows the root as two counted cards', async () => {
    const level = codingEnvironmentView.level!(0, '');
    const host = await render(
      level.card!({
        id: 'environments',
        name: 'environments',
        kind: 'container',
        actions: [],
        size: null,
        modified: null,
        attributes: { count: '4', summary: '4 workspaces across every user' },
      }),
    );

    expect(level.layout).toBe('cards');
    expect(host.textContent).toContain('4');
    expect(host.textContent).toContain('across every user');
  });

  it('shows environments as cards with owner, agent readiness and phase badge', async () => {
    const level = codingEnvironmentView.level!(1, 'environments');
    const host = await render([level.card!(environment), codingEnvironmentView.badges!(environment)]);

    expect(host.textContent).toContain('ada@example.com');
    expect(host.textContent).toContain('Agent ready');
    expect(host.querySelector('.data-pill-success')?.textContent).toContain('running');
  });

  it('lists templates read-only with their active version', async () => {
    const template: ResourceEntry = {
      id: 'templates/tmpl-docker',
      name: 'docker',
      kind: 'item',
      actions: ['read'],
      size: null,
      modified: null,
      attributes: { active_version: 'v-7' },
    };
    const level = codingEnvironmentView.level!(1, 'templates');
    const host = await render([level.columns![0].render(template), codingEnvironmentView.badges!(template)]);

    expect(host.textContent).toContain('v-7');
    expect(host.textContent).toContain('Read-only');
    expect(codingEnvironmentView.nounFor!(template, 1).one).toBe('template');
  });

  it('previews an environment with its owner and lifecycle fields', async () => {
    const detail: ResourceDetail = {
      entry: environment,
      content: null,
      view: {
        type: 'status',
        phase: 'running',
        fields: { Owner: 'ada@example.com', Template: 'docker', Agent: 'Ready', 'Workspace id': 'ws-1' },
        created_at: '2026-10-01T10:00:00Z',
      },
    };
    const host = await render(codingEnvironmentView.preview!(detail, {}));

    expect(host.textContent).toContain('Owner');
    expect(host.textContent).toContain('ws-1');
    expect(host.textContent).toContain('Created');
    expect(codingEnvironmentView.deleteWarning!(environment)).toContain('not pushed');
  });
});
