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
    mounted = await mount(Probe, { api: { access } as unknown as IamAdminApi, scope: 'abi:acme:-' });
    await mounted.flush();

    expect(access).toHaveBeenCalledWith('abi:acme:-');
    expect(mounted.host.textContent).toBe('ready||true|false');
  });

  it('asks nothing while skipped, and again when the reload key changes', async () => {
    const access = vi.fn().mockResolvedValue({ actions: { 'iam:AttachPolicy': true } });
    const api = { access } as unknown as IamAdminApi;
    mounted = await mount(Probe, { api, scope: 'abi:acme:-', skip: true });
    await mounted.flush();
    expect(access).not.toHaveBeenCalled();
    expect(mounted.host.textContent).toBe('ready||false|false');
    await mounted.unmount();

    const host = document.createElement('div');
    document.body.append(host);
    const { createRoot } = await import('react-dom/client');
    const { act } = await import('react');
    const root = createRoot(host);
    await act(async () => root.render(createElement(Probe, { api, scope: 'abi:acme:-', reload: 0 })));
    await act(async () => root.render(createElement(Probe, { api, scope: 'abi:acme:-', reload: 1 })));
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
});
