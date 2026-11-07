// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { WS, attachment } from '../access-fixtures';
import { holdingRows } from './holdings-model';
import { HoldingsTable } from './holdings-table';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('HoldingsTable', () => {
  it('links a policy to its owner only when its owner was read', async () => {
    const rows = holdingRows(
      [
        attachment({ id: 'a1', policy_id: 'pol_known', policy_name: 'Known', scope: WS, policy_owner_scope: WS }),
        attachment({ id: 'a2', policy_id: 'pol_unread', policy_name: 'Unread', scope: WS, policy_owner_scope: null }),
      ],
      [],
    );
    // On the platform's page, where a null owner would read as the platform's own (`actionsKey`).
    const actionsAt = () => ({ 'iam:ListPolicies': true });
    mounted = await mount(HoldingsTable, { rows, names: {}, actionsAt, here: 'abi:', onDetach: vi.fn(), empty: '' });
    const link = (policy: string) => document.querySelector(`[data-holding="${policy}"] a`);
    expect(link('pol_known')?.getAttribute('href')).toBe('/workspace/ws-1/settings/permissions?section=policies&policy=pol_known');
    expect(link('pol_unread')).toBeNull();
    expect(document.querySelector('[data-holding="pol_unread"]')?.textContent).toContain('Unread');
  });
});
