// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/app/settings/system/system-render';
import type { IamAdminApi } from './api';
import { useIamAccess } from './use-access';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

function Probe({ api, scope, skip, reload }: { api: IamAdminApi; scope?: string; skip?: boolean; reload?: number }) {
  const { can, loading, error } = useIamAccess(scope, api, { skip, reload });
  return createElement(
    'p',
    { 'data-probe': true },
    `${loading ? 'loading' : 'ready'}|${error ?? ''}|${can('iam:AttachPolicy')}|${can('iam:CreatePolicy')}`,
  );
}

describe('useIamAccess', () => {
  it('asks for the scope it is given and answers from what IAM says', async () => {
    const access = vi.fn().mockResolvedValue({ actions: { 'iam:AttachPolicy': true, 'iam:CreatePolicy': false } });
    mounted = await mount(Probe, { api: { access } as unknown as IamAdminApi, scope: 'abi:nexus:organization/acme' });
    await mounted.flush();

    expect(access).toHaveBeenCalledWith('abi:nexus:organization/acme');
    expect(mounted.host.textContent).toBe('ready||true|false');
  });

  it('asks nothing while skipped, and again when the reload key changes', async () => {
    const access = vi.fn().mockResolvedValue({ actions: { 'iam:AttachPolicy': true } });
    const api = { access } as unknown as IamAdminApi;
    mounted = await mount(Probe, { api, scope: 'abi:nexus:organization/acme', skip: true });
    await mounted.flush();
    expect(access).not.toHaveBeenCalled();
    expect(mounted.host.textContent).toBe('ready||false|false');
    await mounted.unmount();

    const host = document.createElement('div');
    document.body.append(host);
    const { createRoot } = await import('react-dom/client');
    const { act } = await import('react');
    const root = createRoot(host);
    await act(async () => root.render(createElement(Probe, { api, scope: 'abi:nexus:organization/acme', reload: 0 })));
    await act(async () => root.render(createElement(Probe, { api, scope: 'abi:nexus:organization/acme', reload: 1 })));
    expect(access).toHaveBeenCalledTimes(2);
    await act(async () => root.unmount());
    host.remove();
    mounted = null;
  });

  it('allows nothing until it knows, and when it cannot know', async () => {
    const access = vi.fn().mockRejectedValue(new Error('nope'));
    mounted = await mount(Probe, { api: { access } as unknown as IamAdminApi });

    expect(access).toHaveBeenCalledWith(undefined);
    expect(mounted.host.textContent).toBe('ready|nope|false|false');
  });

  it("is loading for a new scope from its first render, never the previous scope's access", async () => {
    let answer: (value: unknown) => void = () => undefined;
    const access = vi.fn((scope?: string) =>
      scope === 'abi:nexus:organization/owned'
        ? Promise.resolve({ actions: { 'iam:AttachPolicy': true } })
        : new Promise((resolve) => {
            answer = resolve;
          }),
    );
    const api = { access } as unknown as IamAdminApi;
    const host = document.createElement('div');
    document.body.append(host);
    const { createRoot } = await import('react-dom/client');
    const { act } = await import('react');
    const root = createRoot(host);
    const seen: string[] = [];
    const Recorder = ({ scope, skip }: { scope: string; skip?: boolean }) => {
      const { can, loading } = useIamAccess(scope, api, { skip });
      seen.push(`${scope}:${loading ? 'loading' : 'ready'}:${can('iam:AttachPolicy')}`);
      return null;
    };
    await act(async () => root.render(createElement(Recorder, { scope: 'abi:nexus:organization/owned' })));
    expect(seen.at(-1)).toBe('abi:nexus:organization/owned:ready:true');
    seen.length = 0;
    await act(async () => root.render(createElement(Recorder, { scope: 'abi:nexus:organization/other' })));
    // The first render of the new scope already waits, holding nothing of the old one.
    expect(seen[0]).toBe('abi:nexus:organization/other:loading:false');
    expect(seen).not.toContain('abi:nexus:organization/other:ready:true');
    await act(async () => answer({ actions: {} }));
    expect(seen.at(-1)).toBe('abi:nexus:organization/other:ready:false');
    // Skipped, then asked: loading from the render that stops skipping.
    seen.length = 0;
    await act(async () => root.render(createElement(Recorder, { scope: 'abi:nexus:organization/third', skip: true })));
    expect(seen.at(-1)).toBe('abi:nexus:organization/third:ready:false');
    await act(async () => root.render(createElement(Recorder, { scope: 'abi:nexus:organization/third' })));
    expect(seen.at(-1)?.split(':').at(-2)).toBe('loading');
    await act(async () => root.unmount());
    host.remove();
  });
});
