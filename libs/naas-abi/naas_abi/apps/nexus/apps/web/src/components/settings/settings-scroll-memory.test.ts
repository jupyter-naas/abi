// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, createElement, useRef } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { clearPageState } from '@/lib/page-state';
import { clearViewFlag } from '@/lib/view-flag';
import { useAuthStore, type User } from '@/stores/auth';
import { SETTINGS_SCROLLER, useSettingsScrollMemory } from './settings-scroll-memory';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getOllamaUrl: () => 'http://ollama.invalid' }));

const person = (id: string): User => ({ id, email: `${id}@example.invalid`, name: id, createdAt: new Date() });
const signIn = (id: string) => useAuthStore.setState({ user: person(id), csrfToken: `csrf-${id}`, isAuthenticated: true });

/** jsdom lays nothing out: the scroller says how tall its content is. */
let contentHeight = 2_000;

function Shell({ path }: { path: string | null }) {
  const root = useRef<HTMLDivElement>(null);
  useSettingsScrollMemory(root, path);
  return createElement(
    'div',
    { ref: root },
    createElement('div', {
      className: SETTINGS_SCROLLER.slice(1),
      ref: (node: HTMLDivElement | null) => {
        if (!node) return;
        Object.defineProperty(node, 'scrollHeight', { configurable: true, get: () => contentHeight });
        Object.defineProperty(node, 'clientHeight', { configurable: true, get: () => 500 });
      },
    })
  );
}

let host: HTMLDivElement;
let root: Root;
const scroller = () => host.querySelector<HTMLElement>(SETTINGS_SCROLLER)!;
const frames = async (n = 3) => {
  for (let i = 0; i < n; i += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
  }
};
const show = async (path: string | null) => {
  await act(async () => root.render(createElement(Shell, { path })));
  await frames();
};
const scrollTo = async (top: number) => {
  scroller().scrollTop = top;
  scroller().dispatchEvent(new Event('scroll'));
  await frames();
};

beforeEach(async () => {
  clearViewFlag();
  useAuthStore.setState({ user: null, view: null, viewer: null, csrfToken: null, isAuthenticated: false });
  signIn('one');
  clearPageState();
  contentHeight = 2_000;
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

describe('useSettingsScrollMemory', () => {
  it('a page opened again from the column is where it was left; a new page starts at the top', async () => {
    await show('/settings/groups');
    await scrollTo(640);
    await show('/settings/policies');
    expect(scroller().scrollTop).toBe(0);
    await scrollTo(120);

    await show('/settings/groups');
    expect(scroller().scrollTop).toBe(640);
    await show('/settings/policies');
    expect(scroller().scrollTop).toBe(120);
  });

  it('waits for the page to be tall enough (its data arriving) before scrolling back', async () => {
    await show('/settings/groups');
    await scrollTo(1_200);
    await show('/settings/policies');

    contentHeight = 600; // the list is still loading
    await show('/settings/groups');
    expect(scroller().scrollTop).toBeLessThan(1_200);
    contentHeight = 2_000; // it arrived
    await frames();
    expect(scroller().scrollTop).toBe(1_200);
  });

  it('another layout (a level round trip) finds it too: the memory is not the DOM', async () => {
    await show('/account/profile');
    await scrollTo(300);
    await act(async () => root.unmount());
    root = createRoot(host);
    await show('/settings/groups');
    await show('/account/profile');
    expect(scroller().scrollTop).toBe(300);
  });

  it('another account starts at the top', async () => {
    await show('/account/profile');
    await scrollTo(300);
    await show('/account/appearance');
    await act(async () => signIn('two'));
    await show('/account/profile');
    expect(scroller().scrollTop).toBe(0);
  });
});
