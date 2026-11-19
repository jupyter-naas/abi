// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const ready = vi.hoisted(() => {
  let resolve!: (held: boolean) => void;
  const promise = new Promise<boolean>((r) => {
    resolve = r;
  });
  return { promise, resolve };
});
vi.mock('@/lib/web-pass', () => ({ webPassReady: () => ready.promise }));

import { mount } from '@/lib/testing/mount';
import { useWebPassReady } from './use-web-pass-ready';

function Gated() {
  return useWebPassReady() ? createElement('img', { src: '/api/image-data?raw=1&url=x' }) : null;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('useWebPassReady', () => {
  it('keeps a gated tree unrendered until the pass is ready', async () => {
    const view = await mount(Gated, {});
    expect(view.host.querySelector('img')).toBeNull();
    ready.resolve(true);
    await view.flush();
    expect(view.host.querySelector('img')).not.toBeNull();
    await view.unmount();
  });
});
