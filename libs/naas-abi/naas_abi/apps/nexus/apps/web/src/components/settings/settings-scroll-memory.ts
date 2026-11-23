'use client';

import { useEffect, useLayoutEffect, type RefObject } from 'react';
import { readPageState, writePageState, type PageKey } from '@/lib/page-state';

/** The element that scrolls a settings page, in each of the four layouts. */
export const SETTINGS_SCROLLER = '.org-settings-layout-main';

/** How long a return waits for the page to be tall enough (its data loading) to scroll back. */
const RESTORE_DEADLINE_MS = 3_000;
const USER_INPUT = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const;

const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

const scrollKey = (path: string): PageKey => ({ scope: 'settings', page: 'scroll', detail: path });

const nextFrame = (run: () => void): (() => void) => {
  if (typeof requestAnimationFrame === 'function') {
    const frame = requestAnimationFrame(run);
    return () => cancelAnimationFrame(frame);
  }
  const timer = setTimeout(run, 16);
  return () => clearTimeout(timer);
};

/**
 * Each settings page's scroll offset, by path, in the page-state registry: a page opened again
 * (the column, a tab of another level, back/forward) is where it was left; a page not seen yet
 * starts at the top. A return waits for the page to grow to the offset (its data loading),
 * until the user scrolls or a few seconds pass. Nothing is kept during View as or without a
 * known session (the registry's rule).
 */
export function useSettingsScrollMemory(root: RefObject<HTMLElement | null>, path: string | null): void {
  useIsomorphicLayoutEffect(() => {
    const host = root.current;
    if (!host || !path) return;
    const key = scrollKey(path);
    const target = readPageState<number>(key) ?? 0;
    const started = Date.now();
    let restoring = true;
    let cancel: (() => void) | null = null;

    const stop = () => {
      restoring = false;
      cancel?.();
      cancel = null;
    };
    const attempt = () => {
      cancel = null;
      if (!restoring) return;
      const scroller = host.querySelector<HTMLElement>(SETTINGS_SCROLLER);
      if (scroller) {
        const room = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
        scroller.scrollTop = Math.min(target, room);
        if (room >= target) {
          stop();
          return;
        }
      }
      if (Date.now() - started > RESTORE_DEADLINE_MS) {
        stop();
        return;
      }
      cancel = nextFrame(attempt);
    };

    // The offset the user leaves the page at, not one a restore or a shorter page set.
    const onScroll = (event: Event) => {
      if (restoring) return;
      const scroller = event.target;
      if (!(scroller instanceof HTMLElement) || !scroller.matches(SETTINGS_SCROLLER)) return;
      writePageState(key, scroller.scrollTop > 0 ? scroller.scrollTop : undefined);
    };
    // The user scrolls first: their position wins.
    const onInput = () => {
      if (!restoring) return;
      stop();
    };

    host.addEventListener('scroll', onScroll, true);
    USER_INPUT.forEach((name) => host.addEventListener(name, onInput, { capture: true, passive: true }));
    attempt();
    return () => {
      stop();
      host.removeEventListener('scroll', onScroll, true);
      USER_INPUT.forEach((name) => host.removeEventListener(name, onInput, { capture: true }));
    };
  }, [root, path]);
}
