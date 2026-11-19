import { describe, expect, it, vi } from 'vitest';

const redirected = vi.hoisted(() => [] as string[]);

vi.mock('next/navigation', () => ({
  redirect: (to: string) => {
    redirected.push(to);
  },
}));

import DrivesSettingsRedirect from './page';

describe('Workspace settings › Drives', () => {
  it('is gone: its URL opens Workspace settings', async () => {
    await DrivesSettingsRedirect({ params: Promise.resolve({ workspaceId: 'ws-1' }) });
    expect(redirected).toEqual(['/workspace/ws-1/settings/general']);
  });
});
