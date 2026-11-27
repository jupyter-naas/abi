// @vitest-environment jsdom
import { act, createElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { placeHoverTip, useHoverTip } from './hover-tip';

const VIEWPORT = { width: 1280, height: 800 };
const SIZE = { width: 256, height: 60 };
const anchor = (left: number, top: number, width = 200, height = 32) => ({
  left,
  top,
  right: left + width,
  bottom: top + height,
  height,
});

describe('placeHoverTip', () => {
  it('goes right of its anchor, centred on it', () => {
    expect(placeHoverTip(anchor(20, 100), SIZE, VIEWPORT)).toEqual({ top: 86, left: 230, side: 'right' });
  });

  it('goes left when the right has no room, under it when neither side has', () => {
    expect(placeHoverTip(anchor(1100, 100, 160), SIZE, VIEWPORT).side).toBe('left');
    const narrow = { width: 360, height: 640 };
    const under = placeHoverTip(anchor(20, 100, 320), SIZE, narrow);
    expect(under.side).toBe('below');
    expect(under.left + SIZE.width).toBeLessThanOrEqual(narrow.width - 8);
    expect(under.top).toBe(137);
  });

  it('stays inside the screen at its top and bottom edges', () => {
    expect(placeHoverTip(anchor(20, 0, 200, 10), SIZE, VIEWPORT).top).toBe(8);
    expect(placeHoverTip(anchor(20, 790, 200, 10), SIZE, VIEWPORT).top).toBe(800 - 60 - 8);
  });
});

function Anchor({ delay }: { delay?: number }) {
  const tip = useHoverTip({ title: 'Agents', description: 'The agents you may use here', delay });
  return createElement('div', null, createElement('a', { ref: tip.ref, href: '#', ...tip.anchorProps }, 'Agents'), tip.tip);
}

let mounted: Mounted | null = null;
const link = () => mounted!.host.querySelector('a')!;
const tooltip = () => document.querySelector('[role="tooltip"]');
const hover = (el: Element) => act(async () => void el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })));
const leave = (el: Element) =>
  act(async () => void el.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: document.body })));
const wait = (ms: number) => act(async () => void vi.advanceTimersByTime(ms));

describe('useHoverTip', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(async () => {
    await mounted?.unmount();
    mounted = null;
    vi.useRealTimers();
  });

  it('shows the title and description after its delay, and goes on leave', async () => {
    mounted = await mount(Anchor, { delay: 1500 });
    await hover(link());
    await wait(1000);
    expect(tooltip()).toBeNull();
    await wait(600);
    expect(tooltip()?.textContent).toBe('AgentsThe agents you may use here');
    expect(link().getAttribute('aria-describedby')).toBe(tooltip()?.id);
    await leave(link());
    expect(tooltip()).toBeNull();
  });

  it('starts at the edge of its column, touching it, without an entrance effect', async () => {
    function InColumn() {
      const tip = useHoverTip({ title: 'Agents', description: 'The agents you may use here', delay: 0 });
      return createElement(
        'nav',
        { 'data-hover-tip-edge': '' },
        createElement('a', { ref: tip.ref, href: '#', ...tip.anchorProps }, 'Agents'),
        tip.tip
      );
    }
    mounted = await mount(InColumn, {});
    const nav = mounted.host.querySelector('nav')!;
    nav.getBoundingClientRect = () => ({ left: 0, right: 280, top: 0, bottom: 800, width: 280, height: 800, x: 0, y: 0, toJSON: () => ({}) });
    link().getBoundingClientRect = () => ({ left: 16, right: 120, top: 200, bottom: 232, width: 104, height: 32, x: 16, y: 200, toJSON: () => ({}) });
    await hover(link());
    const box = tooltip() as HTMLElement;
    expect(box.style.left).toBe('280px');
    expect(box.className).not.toContain('animate-in');
  });

  it('a press puts it away until the pointer leaves', async () => {
    mounted = await mount(Anchor, { delay: 1500 });
    await hover(link());
    await wait(1600);
    await act(async () => void link().dispatchEvent(new MouseEvent('pointerdown', { bubbles: true })));
    expect(tooltip()).toBeNull();
    await act(async () => void link().dispatchEvent(new FocusEvent('focusin', { bubbles: true })));
    await wait(2000);
    expect(tooltip()).toBeNull();
  });
});
