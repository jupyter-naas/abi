// @vitest-environment jsdom
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const pushed = vi.hoisted(() => ({ paths: [] as string[] }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: (to: string) => { pushed.paths.push(to); },
    prefetch: () => undefined,
  }),
  usePathname: () => '/start',
}));

vi.mock('./dock-profile', () => ({ DockProfile: () => null }));

vi.mock('@/hooks/use-avatar-settings-links', () => ({
  useSettingsHref: () => '/account/profile',
  useWarmAvatarSettingsLinks: () => undefined,
}));

import { mount, type Mounted } from '@/lib/testing/mount';
import { FEATURE_COLUMN_WIDTH_DEFAULT, DOCK_WIDTH_MIN } from '@/lib/shell-columns';
import { useWorkspaceStore } from '@/stores/workspace';
import { Sidebar } from './index';

if (!('ResizeObserver' in globalThis)) {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (globalThis as { ResizeObserver: typeof ResizeObserver }).ResizeObserver = ResizeObserver;
}

let mounted: Mounted | null = null;

beforeEach(() => {
  pushed.paths.length = 0;
  useWorkspaceStore.setState({
    dockWidth: DOCK_WIDTH_MIN,
    currentWorkspaceId: null,
    activePanelSection: null,
  });
  HTMLElement.prototype.setPointerCapture = () => undefined;
  HTMLElement.prototype.releasePointerCapture = () => undefined;
});

afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
  useWorkspaceStore.setState({ dockWidth: DOCK_WIDTH_MIN });
});

function dock(): HTMLElement {
  const aside = mounted?.host.querySelector('aside[aria-label="Dock"]');
  if (!aside) throw new Error('dock missing');
  return aside as HTMLElement;
}

function home(): HTMLButtonElement {
  const button = dock().querySelector('button[aria-label="Home"]');
  if (!(button instanceof HTMLButtonElement)) throw new Error('home missing');
  return button;
}

function labelsVisible(): boolean {
  return (home().textContent ?? '').includes('Home');
}

async function dblclick(el: Element) {
  await act(async () => {
    el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
  });
}

async function pointer(el: Element, type: string, detail: number) {
  await act(async () => {
    el.dispatchEvent(new PointerEvent(type, { bubbles: true, cancelable: true, detail }));
  });
}

describe('dock expand on double-click', () => {
  it('double-click on the bar toggles feature labels', async () => {
    mounted = await mount(Sidebar, {});
    expect(labelsVisible()).toBe(false);
    expect(useWorkspaceStore.getState().dockWidth).toBe(DOCK_WIDTH_MIN);

    await dblclick(dock());
    expect(useWorkspaceStore.getState().dockWidth).toBe(FEATURE_COLUMN_WIDTH_DEFAULT);
    expect(labelsVisible()).toBe(true);

    await dblclick(dock());
    expect(useWorkspaceStore.getState().dockWidth).toBe(DOCK_WIDTH_MIN);
    expect(labelsVisible()).toBe(false);
  });

  it('a click on a logo navigates and does not toggle', async () => {
    mounted = await mount(Sidebar, {});
    await pointer(home(), 'pointerdown', 1);
    await pointer(home(), 'pointerup', 1);
    expect(pushed.paths).toEqual(['/home']);
    expect(useWorkspaceStore.getState().dockWidth).toBe(DOCK_WIDTH_MIN);
    expect(labelsVisible()).toBe(false);
  });

  it('a double-click on a logo does not toggle or navigate twice', async () => {
    mounted = await mount(Sidebar, {});
    await pointer(home(), 'pointerdown', 1);
    await pointer(home(), 'pointerup', 1);
    await pointer(home(), 'pointerdown', 2);
    await pointer(home(), 'pointerup', 2);
    await dblclick(home());
    expect(pushed.paths).toEqual(['/home']);
    expect(useWorkspaceStore.getState().dockWidth).toBe(DOCK_WIDTH_MIN);
    expect(labelsVisible()).toBe(false);
  });
});
