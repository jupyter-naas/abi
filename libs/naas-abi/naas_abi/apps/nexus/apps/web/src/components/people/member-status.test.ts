// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { InvitedBadge, ResendButton } from './member-status';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

describe('the Invited badge', () => {
  it('shows for an invited person only', async () => {
    mounted = await mount(InvitedBadge, { status: 'invited' });
    expect(mounted.host.querySelector('[data-status="invited"]')?.textContent).toBe('Invited');
    await mounted.unmount();
    mounted = await mount(InvitedBadge, { status: 'active' });
    expect(mounted.host.textContent).toBe('');
  });
});

describe('Resend', () => {
  it('emails them again and says so', async () => {
    const resend = vi.fn(async () => true);
    const onDone = vi.fn();
    mounted = await mount(ResendButton, { email: 'bob@example.com', resend, onDone, onError: vi.fn() });
    await mounted.click(mounted.host.querySelector('[data-action="resend"]'));
    await mounted.flush();
    expect(resend).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledWith('Sign-in email sent again to bob@example.com.');
  });

  it('says what the API refused (someone active)', async () => {
    const onError = vi.fn();
    mounted = await mount(ResendButton, {
      email: 'bob@example.com',
      resend: async () => {
        throw new Error('Already signed in');
      },
      onDone: vi.fn(),
      onError,
    });
    await mounted.click(mounted.host.querySelector('[data-action="resend"]'));
    await mounted.flush();
    expect(onError).toHaveBeenCalledWith('Already signed in');
  });
});
