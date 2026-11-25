// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { RolesLoadingNote, useProgressiveRoles, type RolesBatch } from './use-progressive-roles';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const PEOPLE = Array.from({ length: 250 }, (_, i) => `prn_${i}`);

function List({ all, page, fetchRoles }: { all: string[]; page: string[]; fetchRoles: RolesBatch<string> }) {
  const roles = useProgressiveRoles(all, fetchRoles);
  roles.show(page);
  return createElement(
    'div',
    null,
    createElement(RolesLoadingNote, { roles }),
    createElement('ul', null, ...page.map((p) => createElement('li', { key: p, 'data-row': p }, roles.of(p)?.join(',') ?? 'pending')))
  );
}

describe('a Users list’s roles, read a page first', () => {
  it('reads the page shown first, then the others a hundred at a time', async () => {
    const asked: string[][] = [];
    const fetchRoles = vi.fn(async (batch: string[]) => {
      asked.push(batch);
      return Object.fromEntries(batch.map((p) => [p, [`role of ${p}`]]));
    });
    const page = PEOPLE.slice(200, 220);
    mounted = await mount(List, { all: PEOPLE, page, fetchRoles });
    await mounted.flush();
    await mounted.flush();
    await mounted.flush();
    expect(asked[0].slice(0, 20)).toEqual(page);
    expect(asked.map((b) => b.length)).toEqual([100, 100, 50]);
    expect(new Set(asked.flat()).size).toBe(250);
    expect(mounted.host.querySelector('[data-row="prn_200"]')?.textContent).toBe('role of prn_200');
    expect(mounted.host.querySelector('[data-field="roles-loading"]')).toBeNull();
  });

  it('says how many are read while it reads, and a failure', async () => {
    let release: () => void = () => undefined;
    const fetchRoles = vi.fn(
      (batch: string[]) =>
        new Promise<Record<string, string[]>>((resolve, reject) => {
          if (batch.includes('prn_100')) {
            release = () => reject(new Error('Not allowed'));
            return;
          }
          resolve(Object.fromEntries(batch.map((p) => [p, ['Members']])));
        })
    );
    mounted = await mount(List, { all: PEOPLE, page: PEOPLE.slice(0, 20), fetchRoles });
    await mounted.flush();
    expect(mounted.host.querySelector('[data-field="roles-loading"]')?.textContent).toContain('Roles loading 100/250');
    release();
    await mounted.flush();
    expect(mounted.host.querySelector('[data-field="roles-loading"]')?.textContent).toContain('Not allowed');
  });
});
