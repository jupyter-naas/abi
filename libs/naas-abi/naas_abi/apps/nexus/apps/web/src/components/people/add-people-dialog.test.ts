// @vitest-environment jsdom
import { act } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { MemberCandidate, PeopleApi } from '@/lib/people';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

import { AddPeopleDialog } from './add-people-dialog';

const FLO: MemberCandidate = {
  user_id: 'usr_flo',
  name: 'Florent',
  email: 'florent@naas.ai',
  avatar: null,
  status: 'active',
  org_role: 'member',
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

function fakeApi() {
  const candidates = vi.fn(async (_ws: string, q: string) =>
    [FLO].filter((c) => `${c.name} ${c.email}`.toLowerCase().includes(q.toLowerCase()))
  );
  const addMember = vi.fn(async () => ({ member: { id: 'm' }, emailSent: true }));
  return { candidates, addMember } satisfies Pick<PeopleApi, 'candidates' | 'addMember'>;
}

async function render(open = true) {
  const api = fakeApi();
  const props = {
    open,
    onClose: vi.fn(),
    onAdded: vi.fn(),
    navigate: vi.fn(),
    workspaceId: 'ws-1',
    api,
    searchDelayMs: 0,
  };
  mounted = await mount(AddPeopleDialog, props);
  return { api, ...props };
}

const dialog = () => document.body.querySelector<HTMLElement>('[role="dialog"]');
const input = () => dialog()!.querySelector<HTMLInputElement>('input[role="combobox"]')!;

describe('Add people dialog', () => {
  it('shows nothing while closed', async () => {
    await render(false);
    expect(dialog()).toBeNull();
  });

  it('asks for the name or email of the person, in a modal dialog', async () => {
    await render();
    expect(dialog()?.getAttribute('aria-modal')).toBe('true');
    expect(dialog()?.textContent).toContain('Invite user');
    expect(input()).not.toBeNull();
  });

  it('adds the person picked, then says so and closes', async () => {
    const { api, onAdded, onClose } = await render();
    await mounted!.type(input(), 'Flo');
    await mounted!.flush();
    await mounted!.flush();
    const option = dialog()!.querySelector('[role="option"]');
    expect(option?.textContent).toContain('Florent');
    await mounted!.click(option);
    await mounted!.click(dialog()!.querySelector('[data-action="invite"]'));
    await mounted!.flush();
    expect(api.addMember).toHaveBeenCalledWith('ws-1', expect.objectContaining({ userId: 'usr_flo' }));
    expect(onAdded).toHaveBeenCalledWith(FLO, true);
    expect(onClose).toHaveBeenCalled();
  });

  it('closes with Escape, and with Cancel', async () => {
    const { onClose } = await render();
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(onClose).toHaveBeenCalledTimes(1);
    await mounted!.click(dialog()!.querySelector('[data-action="close"]'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
