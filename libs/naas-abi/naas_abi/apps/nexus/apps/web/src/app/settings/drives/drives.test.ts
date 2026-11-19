// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { PlatformDrives } from './drives';
import { DRIVES_API } from './drives-api';

const FILE_SYSTEM = {
  id: 'file-system',
  name: 'File System',
  type: 'Object storage',
  provider: 'MinIO (S3-compatible)',
  adapter: 's3',
  location: [
    { label: 'bucket', value: 'abi' },
    { label: 'prefix', value: 'datastore' },
  ],
  status: 'reachable',
};

function api(status: number, body: unknown) {
  const calls: string[] = [];
  const fetcher = async (url: string) => {
    calls.push(url);
    return new Response(JSON.stringify(body), { status });
  };
  return { fetcher, calls };
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const row = (id: string) => mounted!.host.querySelector(`tr[data-drive="${id}"]`);
const field = (id: string, name: string) => row(id)?.querySelector(`[data-field="${name}"]`)?.textContent;

describe('PlatformDrives', () => {
  it('shows the File System row: type, provider, location and status', async () => {
    const { fetcher, calls } = api(200, [FILE_SYSTEM]);
    mounted = await mount(PlatformDrives, { fetcher });
    await mounted.flush();
    expect(calls).toEqual([DRIVES_API]);
    expect(mounted.host.querySelector('h2')?.textContent).toBe('Drives');
    expect(mounted.host.textContent).toContain('1 drive');
    expect(field('file-system', 'name')).toBe('File System');
    expect(field('file-system', 'type')).toBe('Object storage');
    expect(field('file-system', 'provider')).toBe('MinIO (S3-compatible)');
    expect(field('file-system', 'location')).toContain('bucket');
    expect(field('file-system', 'location')).toContain('abi');
    expect(field('file-system', 'location')).toContain('prefix');
    expect(field('file-system', 'location')).toContain('datastore');
    expect(field('file-system', 'status')).toBe('Reachable');
  });

  it('is read-only: no switch, no edit', async () => {
    const { fetcher } = api(200, [FILE_SYSTEM]);
    mounted = await mount(PlatformDrives, { fetcher });
    await mounted.flush();
    expect(row('file-system')?.querySelector('input, [role="checkbox"], [role="switch"]')).toBeNull();
    expect(mounted.host.textContent).not.toMatch(/access key|secret/i);
  });

  it('marks a storage that does not answer', async () => {
    const { fetcher } = api(200, [{ ...FILE_SYSTEM, status: 'unreachable' }]);
    mounted = await mount(PlatformDrives, { fetcher });
    await mounted.flush();
    expect(field('file-system', 'status')).toBe('Unreachable');
    expect(row('file-system')?.querySelector('[data-field="status"]')?.className).toContain('is-unreachable');
  });

  it('says why when the API refuses', async () => {
    const { fetcher } = api(403, { detail: '' });
    mounted = await mount(PlatformDrives, { fetcher });
    await mounted.flush();
    expect(mounted.host.querySelector('[role="alert"]')?.textContent).toContain(
      'Only a platform admin can list the drives.'
    );
    expect(mounted.host.querySelector('tr[data-drive]')).toBeNull();
  });

  it('asks again on refresh', async () => {
    const { fetcher, calls } = api(200, [FILE_SYSTEM]);
    mounted = await mount(PlatformDrives, { fetcher });
    await mounted.flush();
    await mounted.click(mounted.host.querySelector('[data-action="refresh"]'));
    await mounted.flush();
    expect(calls).toEqual([DRIVES_API, DRIVES_API]);
  });
});
