// @vitest-environment jsdom
import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { MemberCandidate, PeopleApi } from '@/lib/people';

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));

import { AddPeople } from './add-people';

const FLO: MemberCandidate = {
  user_id: 'usr_flo',
  name: 'Florent',
  email: 'florent@naas.ai',
  avatar: null,
  status: 'active',
  org_role: 'member',
};
const FLO2: MemberCandidate = {
  user_id: 'usr_flo2',
  name: 'Florent F',
  email: 'florent.frvservices@gmail.com',
  avatar: '/avatars/flo2.png',
  status: 'invited',
  org_role: null,
};

let mounted: Mounted | null = null;
afterEach(async () => {
  vi.useRealTimers();
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

function fakeApi(items: MemberCandidate[] = [FLO, FLO2]) {
  const candidates = vi.fn(async (_ws: string, q: string) =>
    items.filter((c) => `${c.name} ${c.email}`.toLowerCase().includes(q.toLowerCase()))
  );
  const addMember = vi.fn(async () => ({ member: { id: 'm' }, emailSent: true }));
  return { candidates, addMember } satisfies Pick<PeopleApi, 'candidates' | 'addMember'>;
}

async function render(props: Partial<Parameters<typeof AddPeople>[0]> = {}) {
  const api = props.api ?? fakeApi();
  const navigate = vi.fn();
  const onAdded = vi.fn();
  mounted = await mount(AddPeople, {
    workspaceId: 'ws-1',
    navigate,
    onAdded,
    api,
    searchDelayMs: 0,
    ...props,
  });
  return { api, navigate, onAdded };
}

const input = () => mounted!.host.querySelector<HTMLInputElement>('input[role="combobox"]')!;
const options = () => [...mounted!.host.querySelectorAll('[role="option"]')];
const key = async (k: string) =>
  act(async () => {
    input().dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  });

async function typeAndSettle(text: string) {
  await mounted!.type(input(), text);
  await mounted!.flush();
  await mounted!.flush();
}

describe('Add people', () => {
  it('asks nothing below two characters', async () => {
    const { api } = await render();
    await typeAndSettle('F');
    expect(api.candidates).not.toHaveBeenCalled();
    expect(input().getAttribute('aria-expanded')).toBe('false');
  });

  it('asks once the typing stops (debounced)', async () => {
    vi.useFakeTimers();
    const { api } = await render({ searchDelayMs: 250 });
    await mounted!.type(input(), 'Fl');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    await mounted!.type(input(), 'Flo');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(249);
    });
    expect(api.candidates).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(api.candidates).toHaveBeenCalledTimes(1);
    expect(api.candidates.mock.calls[0].slice(0, 2)).toEqual(['ws-1', 'Flo']);
  });

  it('lists the suggestions as a WAI-ARIA combobox: avatar, name, email, Invited', async () => {
    await render();
    await typeAndSettle('Flo');
    const box = input();
    expect(box.getAttribute('aria-expanded')).toBe('true');
    const listbox = mounted!.host.querySelector(`#${CSS.escape(box.getAttribute('aria-controls')!)}`);
    expect(listbox?.getAttribute('role')).toBe('listbox');
    expect(options().map((o) => o.textContent)).toEqual([
      'FFlorentflorent@naas.ai',
      'Florent FInvitedflorent.frvservices@gmail.com',
    ]);
    expect(options()[1].querySelector('img')?.getAttribute('src')).toBe('https://api.example.test/avatars/flo2.png');
  });

  it('leaves out the members already here, and says so', async () => {
    await render({ memberIds: new Set(['usr_flo']) });
    await typeAndSettle('Flo');
    expect(options().map((o) => o.textContent)).toEqual([
      'Florent FInvitedflorent.frvservices@gmail.com',
    ]);
    expect(mounted!.host.querySelector('[data-excluded]')?.textContent).toBe('1 match is already a member here.');
  });

  it('moves with the arrows and picks with Enter', async () => {
    const { api } = await render();
    await typeAndSettle('Flo');
    await key('ArrowDown');
    expect(options()[0].getAttribute('aria-selected')).toBe('true');
    expect(input().getAttribute('aria-activedescendant')).toBe(options()[0].id);
    await key('ArrowDown');
    await key('ArrowDown');
    expect(options()[0].getAttribute('aria-selected')).toBe('true');
    await key('ArrowUp');
    expect(options()[1].getAttribute('aria-selected')).toBe('true');
    await key('Enter');
    await mounted!.flush();
    expect(api.addMember).toHaveBeenCalledWith('ws-1', expect.objectContaining({ userId: 'usr_flo2' }));
  });

  it('closes the list with Escape', async () => {
    await render();
    await typeAndSettle('Flo');
    await key('Escape');
    expect(input().getAttribute('aria-expanded')).toBe('false');
    expect(input().hasAttribute('aria-controls')).toBe(false);
    expect(options()).toEqual([]);
  });

  it('adds the person picked to the workspace at once, keeping their level, then says so', async () => {
    const { api, onAdded } = await render();
    await typeAndSettle('Flo');
    await mounted!.click(options()[0]);
    await mounted!.flush();
    expect(api.addMember).toHaveBeenCalledWith('ws-1', { userId: 'usr_flo', level: null, admin: false, capabilities: [] });
    expect(onAdded).toHaveBeenCalledWith(FLO, true);
    expect(input().value).toBe('');
    expect(mounted!.host.querySelector('[data-field="level"]')).toBeNull();
    expect(document.activeElement).toBe(input());
  });

  it('shows what the API refused', async () => {
    const api = fakeApi();
    api.addMember.mockRejectedValueOnce(new Error('Already a member of this workspace'));
    await render({ api });
    await typeAndSettle('Flo');
    await mounted!.click(options()[0]);
    await mounted!.flush();
    expect(mounted!.host.textContent).toContain('Already a member of this workspace');
  });

  it("opens the create page prefilled from Create user '<text>' when nobody matches", async () => {
    const { navigate } = await render();
    await typeAndSettle('zoe@other.org');
    expect(options().map((o) => o.textContent)).toEqual(["Create user 'zoe@other.org'"]);
    await key('ArrowDown');
    await key('Enter');
    expect(navigate).toHaveBeenCalledWith('/workspace/ws-1/settings/users/new?email=zoe%40other.org');
  });

  it('offers a Create user button when nobody matches, opening the create page prefilled', async () => {
    const { navigate } = await render();
    await typeAndSettle('Florent');
    expect(mounted!.host.querySelector('[data-action="create"]')).toBeNull();
    await typeAndSettle('zoe@other.org');
    const create = mounted!.host.querySelector<HTMLButtonElement>('[data-action="create"]');
    expect(create?.textContent).toContain('Create user');
    expect(mounted!.host.querySelector('[data-add-people-create]')?.textContent).toContain('zoe@other.org');
    await mounted!.click(create);
    expect(navigate).toHaveBeenCalledWith('/workspace/ws-1/settings/users/new?email=zoe%40other.org');
  });
});
