// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { IamAdminError } from '@/lib/iam-admin/api';
import { mount, type Mounted } from '@/app/settings/system/system-render';
import { fakeApi } from '@/components/access/access-fixtures';
import { setsView } from '@/app/settings/modules/sets-fixtures';
import { OrgModulesView } from './modules';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('OrgModulesView', () => {
  it('shows the organization’s matrix, its workspace column highlighted', async () => {
    const sets = vi.fn().mockResolvedValue(setsView);
    mounted = await mount(OrgModulesView, { api: fakeApi({ sets }), orgId: 'org-1', workspaceId: 'ws-1' });
    await mounted.flush();
    expect(sets).toHaveBeenCalledWith('org-1');
    expect(document.querySelector('[data-sets-column="org-1"]')).not.toBeNull();
    expect(document.querySelector('[data-sets-column="ws-1"]')!.className).toContain('sets-matrix-col-highlight');
  });

  it('says the caller cannot view the modules on a 403', async () => {
    const sets = vi.fn().mockRejectedValue(new IamAdminError('Not allowed', 403));
    mounted = await mount(OrgModulesView, { api: fakeApi({ sets }), orgId: 'org-1' });
    await mounted.flush();
    expect(document.body.textContent).toContain('You cannot view this organization’s modules');
    expect(document.querySelector('[data-sets-column]')).toBeNull();
  });

  it('shows any other failure as it is', async () => {
    const sets = vi.fn().mockRejectedValue(new IamAdminError('IAM is not available on this server.', 503));
    mounted = await mount(OrgModulesView, { api: fakeApi({ sets }), orgId: 'org-1' });
    await mounted.flush();
    expect(document.querySelector('[role="alert"]')?.textContent).toBe('IAM is not available on this server.');
  });
});
