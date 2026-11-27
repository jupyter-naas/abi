// @vitest-environment jsdom
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { SearchPicker } from './search-picker';

let mounted: Mounted | null = null;
beforeAll(() => {
  // jsdom has no ResizeObserver.
  globalThis.ResizeObserver ??= class { observe() {} disconnect() {} unobserve() {} } as unknown as typeof ResizeObserver;
  Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
  Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true });
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const PROPS = {
  single: true,
  items: [
    { value: 'w', label: 'EDF access' },
    { value: 'p', label: 'Sales access' },
  ],
  value: ['w'],
  onToggle: () => undefined,
  onClear: () => undefined,
  loading: false,
  error: null,
  label: 'EDF access',
  noun: 'policies',
};

async function openAt(top: number) {
  mounted = await mount(SearchPicker, PROPS);
  const wrap = mounted.host.querySelector('.search-picker') as HTMLElement;
  wrap.getBoundingClientRect = () => ({ top, bottom: top + 32, left: 16, right: 256, width: 240, height: 32, x: 16, y: top, toJSON: () => ({}) });
  await mounted.click(mounted.host.querySelector('.search-picker-trigger'));
  return document.querySelector('[role="listbox"]')!.closest('.fixed') as HTMLElement;
}

describe('SearchPicker, where its list opens', () => {
  it('under its trigger when there is room, by its top', async () => {
    const popup = await openAt(100);
    expect(popup.style.top).toBe('136px');
    expect(popup.style.bottom).toBe('');
  });

  it('above it near the bottom of the screen, by its bottom: a short list hugs the trigger', async () => {
    const popup = await openAt(700);
    expect(popup.style.bottom).toBe(`${800 - 700 + 4}px`);
    expect(popup.style.top).toBe('');
  });
});
