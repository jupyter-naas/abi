// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const nav = vi.hoisted(() => ({ search: new URLSearchParams('policy=pol-sales') }));
vi.mock('next/navigation', () => ({
  useSearchParams: () => nav.search,
  useRouter: () => ({ push: vi.fn(), prefetch: vi.fn() }),
}));

import { InstanceBack } from './instance-form';
import { ModuleLink } from './module-link';
import { usePolicyHref } from './use-policy-href';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  nav.search = new URLSearchParams('policy=pol-sales');
});

function Probe({ hrefs }: { hrefs: string[] }) {
  const policyHref = usePolicyHref();
  return createElement('ul', null, ...hrefs.map((href) => createElement('li', { key: href }, policyHref(href))));
}
const texts = (m: Mounted) => [...m.host.querySelectorAll('li')].map((li) => li.textContent);

describe('usePolicyHref', () => {
  it('carries the policy picked to the pages it drives, not to the others', async () => {
    mounted = await mount(Probe, {
      hrefs: [
        '/workspace/ws-1/settings/search',
        '/workspace/ws-1/settings/search/topics/t1',
        '/workspace/ws-1/settings/modules?module=acme.sales',
        '/workspace/ws-1/settings/general',
      ],
    });
    expect(texts(mounted)).toEqual([
      '/workspace/ws-1/settings/search?policy=pol-sales',
      '/workspace/ws-1/settings/search/topics/t1?policy=pol-sales',
      '/workspace/ws-1/settings/modules?module=acme.sales&policy=pol-sales',
      '/workspace/ws-1/settings/general',
    ]);
  });

  it('leaves every link as is under "<W> access"', async () => {
    nav.search = new URLSearchParams('');
    mounted = await mount(Probe, { hrefs: ['/workspace/ws-1/settings/agents'] });
    expect(texts(mounted)).toEqual(['/workspace/ws-1/settings/agents']);
  });

  it('keeps the policy on an instance page\'s Back and on a module\'s link', async () => {
    mounted = await mount(() =>
      createElement(
        'div',
        null,
        createElement(InstanceBack, { href: '/workspace/ws-1/settings/maps', label: 'Maps' }),
        createElement(ModuleLink, { workspaceId: 'ws-1', module: 'acme.sales' })
      ), {});
    const hrefs = [...mounted.host.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual([
      '/workspace/ws-1/settings/maps?policy=pol-sales',
      '/workspace/ws-1/settings/modules?module=acme.sales&policy=pol-sales',
    ]);
  });
});
