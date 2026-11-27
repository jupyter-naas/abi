// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessApi } from '@/app/workspace/[workspaceId]/settings/features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '@/app/workspace/[workspaceId]/settings/features/feature-access-model';
import { PlatformFeatures } from './platform-features';

const row = (key: string, label: string, choice: 'everyone' | 'nobody'): FeatureRow =>
  ({
    key,
    label,
    choice,
    principals: [],
    policy: null,
    hand_edited: false,
    offered: true,
    held: true,
    editable: true,
    reason: null,
    also: [],
  }) as FeatureRow;

const ACCESS = { id: 'pol_platform', name: 'Platform access', owner_scope: 'abi:' };
const state = (rows: FeatureRow[]): FeatureAccessState =>
  ({
    workspace_id: 'abi:',
    scope: 'abi:',
    access_policy: ACCESS,
    policy: ACCESS,
    policies: [ACCESS],
    members_group: null,
    can: { create: true, attach: true, detach: true, widen: true },
    features: rows,
  }) as FeatureAccessState;

const BEFORE = state([row('chat', 'Chat', 'everyone'), row('sheets', 'Sheets', 'nobody'), row('tasks', 'Tasks', 'nobody')]);

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Platform › Access › Features, the platform picked', () => {
  it('lists every feature, offered or not, and offers one at once', async () => {
    const save = vi.fn(async () => state([row('chat', 'Chat', 'everyone'), row('sheets', 'Sheets', 'everyone'), row('tasks', 'Tasks', 'nobody')]));
    const api = { read: vi.fn(async () => BEFORE), save } as unknown as FeatureAccessApi;
    mounted = await mount(PlatformFeatures, { api });
    await mounted.flush();
    expect(api.read).toHaveBeenCalledWith('platform');
    expect(mounted.host.textContent).toContain('3 features');
    const box = (key: string) => mounted!.host.querySelector<HTMLInputElement>(`[data-offered="${key}"]`)!;
    expect(box('chat').checked).toBe(true);
    expect(box('sheets').checked).toBe(false);
    await mounted.click(box('sheets'));
    await mounted.flush();
    expect(save).toHaveBeenCalledWith('platform', [{ feature: 'sheets', choice: 'everyone', principals: [] }]);
    expect(box('sheets').checked).toBe(true);
    expect(mounted.host.querySelector('[data-platform-features-notice]')?.textContent).toBe('1 feature offered.');
  });
});
