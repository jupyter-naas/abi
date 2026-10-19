// @vitest-environment jsdom
import { createElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/app/workspace/[workspaceId]/admin/system/system-render';
import type { IamAdminApi } from './api';
import { useIamAccess } from './use-access';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

function Probe({ api, scope }: { api: IamAdminApi; scope?: string }) {
  const { can, loading, error } = useIamAccess(scope, api);
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

  it('allows nothing until it knows, and when it cannot know', async () => {
    const access = vi.fn().mockRejectedValue(new Error('nope'));
    mounted = await mount(Probe, { api: { access } as unknown as IamAdminApi });

    expect(access).toHaveBeenCalledWith(undefined);
    expect(mounted.host.textContent).toBe('ready|nope|false|false');
  });
});
