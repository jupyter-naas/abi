// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import { account, fakeApi, key, allowAll } from '../service-fixtures';
import { ServiceAccountsView } from './service-accounts';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const SECRET = 'abi_sk_k2_SUPERSECRETVALUE';

const buttonNamed = (label: string) =>
  [...document.querySelectorAll('button')].find(
    (b) => b.textContent?.trim() === label || b.getAttribute('aria-label') === label,
  ) ?? null;

function setup(extra: Record<string, unknown> = {}) {
  const keys = [key()];
  const api = fakeApi({
    listServiceAccounts: vi.fn(() => Promise.resolve({ items: [account(), account({ id: 'sa_2', name: 'etl' })] })),
    listKeys: vi.fn(() => Promise.resolve({ items: keys })),
    createKey: vi.fn(() => Promise.resolve({ key: key({ id: 'k2', prefix: 'abi_sk_k2' }), value: SECRET })),
    rotateKey: vi.fn(() => Promise.resolve({ key: key({ id: 'k3', prefix: 'abi_sk_k3' }), value: SECRET + '_ROT' })),
    revokeKey: vi.fn(() => Promise.resolve(key({ status: 'revoked' }))),
    ...extra,
  });
  return api;
}

async function openAccount(m: Mounted, name: string) {
  const row = m.host.querySelector(`[data-service-account="${name}"]`);
  await m.click(row?.querySelector('button.system-row-toggle') ?? null);
  await m.flush();
}

describe('ServiceAccountsView keys', () => {
  it('shows a new key once, with a warning, and never in the list', async () => {
    const api = setup();
    mounted = await mount(ServiceAccountsView, { api, can: allowAll });
    await mounted.flush();
    await openAccount(mounted, 'ci');

    await mounted.type(document.querySelector('[aria-label="Key description"]'), 'deploy');
    await mounted.click(buttonNamed('Create key'));
    await mounted.flush();

    expect(api.createKey).toHaveBeenCalledWith('sa_1', { description: 'deploy' });
    const panel = document.querySelector('[data-one-time-secret]');
    expect(panel?.textContent).toContain(SECRET);
    expect(panel?.textContent).toContain('shown only once');
    const rows = [...document.querySelectorAll('[data-key-id]')].map((r) => r.textContent).join('');
    expect(rows).toContain('abi_sk_k1');
    expect(rows).not.toContain(SECRET);

    await mounted.click(buttonNamed('I have copied it'));
    expect(document.body.textContent).not.toContain(SECRET);
    expect(document.body.innerHTML).not.toContain('SUPERSECRET');
  });

  it('forgets an uncopied value when the account is closed or another is opened', async () => {
    const api = setup();
    mounted = await mount(ServiceAccountsView, { api, can: allowAll });
    await mounted.flush();
    await openAccount(mounted, 'ci');
    await mounted.click(buttonNamed('Create key'));
    await mounted.flush();
    expect(document.body.textContent).toContain(SECRET);

    await openAccount(mounted, 'etl');
    expect(document.body.textContent).not.toContain(SECRET);
    await openAccount(mounted, 'ci');
    expect(document.body.textContent).not.toContain(SECRET);
  });

  it('forgets the value when the views are refreshed or unmounted, and keeps it nowhere', async () => {
    const api = setup();
    mounted = await mount(ServiceAccountsView, { api, can: allowAll });
    await mounted.flush();
    await openAccount(mounted, 'ci');
    await mounted.click(buttonNamed('Create key'));
    await mounted.flush();
    expect(document.body.textContent).toContain(SECRET);

    await mounted.unmount();
    expect(document.body.textContent).not.toContain(SECRET);
    mounted = null;
    expect(JSON.stringify({ ...localStorage })).not.toContain('SUPERSECRET');
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('SUPERSECRET');
    expect(location.href).not.toContain('SUPERSECRET');
  });

  it('shows a rotated key once and revokes through the API', async () => {
    const api = setup();
    mounted = await mount(ServiceAccountsView, { api, can: allowAll });
    await mounted.flush();
    await openAccount(mounted, 'ci');

    await mounted.click(buttonNamed('Rotate abi_sk_k1'));
    await mounted.flush();
    expect(api.rotateKey).toHaveBeenCalledWith('sa_1', 'k1');
    expect(document.querySelector('[data-one-time-secret]')?.textContent).toContain(`${SECRET}_ROT`);
    await mounted.click(buttonNamed('I have copied it'));
    expect(document.body.textContent).not.toContain('_ROT');

    await mounted.click(buttonNamed('Revoke abi_sk_k1'));
    await mounted.flush();
    expect(api.revokeKey).toHaveBeenCalledWith('sa_1', 'k1');
  });

  it('offers no key buttons without the rights', async () => {
    const api = setup();
    mounted = await mount(ServiceAccountsView, { api, can: () => false });
    await mounted.flush();
    await openAccount(mounted, 'ci');
    expect(buttonNamed('Create key')).toBeNull();
    expect(buttonNamed('Revoke abi_sk_k1')).toBeNull();
    expect(buttonNamed('Rotate abi_sk_k1')).toBeNull();
  });
});

describe('ServiceAccountsView accounts', () => {
  it('deletes after the name is typed back, never a builtin one', async () => {
    const deleteServiceAccount = vi.fn(() => Promise.resolve());
    const api = setup({
      deleteServiceAccount,
      listServiceAccounts: vi.fn(() =>
        Promise.resolve({ items: [account(), account({ id: 'sa_e', name: 'engine', account_kind: 'builtin' })] }),
      ),
    });
    mounted = await mount(ServiceAccountsView, { api, can: allowAll });
    await mounted.flush();
    expect(buttonNamed('Delete engine')).toBeNull();

    await mounted.click(buttonNamed('Delete ci'));
    const confirm = () => buttonNamed('Delete service account') as HTMLButtonElement;
    expect(confirm().disabled).toBe(true);
    await mounted.type(document.querySelector('[aria-label="Type the name to confirm"]'), 'ci');
    await mounted.click(confirm());
    expect(deleteServiceAccount).toHaveBeenCalledWith('sa_1');
  });
});
