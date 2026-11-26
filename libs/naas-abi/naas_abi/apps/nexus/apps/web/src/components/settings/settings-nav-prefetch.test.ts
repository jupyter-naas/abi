// @vitest-environment jsdom
/**
 * The Settings column prefetches a page on intent only (#1609): a link the pointer rests
 * on, the keyboard reaches or a finger touches, never every link of the column as it
 * scrolls into view. A route prefetch loads code and the route's payload; it runs no
 * effect, so it never synchronizes agents, reveals a secret, creates a key or opens a stream.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, createElement } from 'react';
import { Bot, KeyRound } from 'lucide-react';
import { mount, type Mounted } from '@/lib/testing/mount';

const nav = vi.hoisted(() => ({ prefetched: [] as string[], linkPrefetch: [] as unknown[] }));

vi.mock('next/link', async () => {
  const { createElement } = await import('react');
  return {
    default: ({ href, children, prefetch, ...rest }: { href: string; children: unknown; prefetch?: unknown }) => {
      nav.linkPrefetch.push(prefetch);
      return createElement('a', { href, ...rest }, children as never);
    },
  };
});
vi.mock('next/navigation', () => ({
  useRouter: () => ({ prefetch: (href: string) => nav.prefetched.push(href), push: vi.fn() }),
}));

import { SettingsNavItem } from './settings-shell';

function Column() {
  return createElement(
    'ul',
    null,
    createElement(SettingsNavItem, { href: '/workspace/ws/settings/agents', label: 'Agents', icon: Bot, active: false }),
    createElement(SettingsNavItem, { href: '/workspace/ws/settings/secrets', label: 'Secrets', icon: KeyRound, active: false }),
  );
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  nav.prefetched = [];
  nav.linkPrefetch = [];
});

const link = (label: string) =>
  [...document.querySelectorAll('a')].find((a) => a.textContent?.includes(label)) as HTMLAnchorElement;

describe('Settings column prefetch', () => {
  it('prefetches nothing as the column renders', async () => {
    mounted = await mount(Column, {});
    expect(nav.linkPrefetch).toEqual([false, false]);
    expect(nav.prefetched).toEqual([]);
  });

  it('prefetches the page a link leads to on hover, focus or touch', async () => {
    mounted = await mount(Column, {});
    await act(async () => {
      link('Agents').dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    });
    expect(nav.prefetched).toEqual(['/workspace/ws/settings/agents']);

    await act(async () => link('Secrets').focus());
    expect(nav.prefetched).toEqual(['/workspace/ws/settings/agents', '/workspace/ws/settings/secrets']);
  });
});
