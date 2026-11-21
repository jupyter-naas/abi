// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import {
  createPlatformFilesApi,
  PlatformFilesError,
  type PlatformFilesApi,
  type PlatformFilesState,
} from './platform-files-api';
import { PlatformFiles } from './platform-files';

const state = (over: Partial<PlatformFilesState> = {}): PlatformFilesState => ({
  workspace_id: 'ws1',
  mode: 'off',
  can_change: false,
  ...over,
});

function fakeApi(read: PlatformFilesState | Error, saved?: PlatformFilesState | Error) {
  const answer = (value: PlatformFilesState | Error | undefined) =>
    value instanceof Error ? vi.fn().mockRejectedValue(value) : vi.fn().mockResolvedValue(value);
  return { read: answer(read), save: answer(saved ?? read) };
}

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

async function render(api: ReturnType<typeof fakeApi>) {
  mounted = await mount(PlatformFiles, { workspaceId: 'ws1', api: api as unknown as PlatformFilesApi });
  await mounted.flush();
  return mounted;
}

const choice = (m: Mounted, mode: string) =>
  m.host.querySelector(`[data-platform-files="${mode}"]`) as HTMLButtonElement | null;

describe('PlatformFiles', () => {
  it('shows the mode read-only to a workspace admin', async () => {
    const m = await render(fakeApi(state({ mode: 'read' })));

    expect(['off', 'read', 'write'].map((mode) => choice(m, mode)?.textContent)).toEqual([
      'Off',
      'Read',
      'Read and write',
    ]);
    expect(choice(m, 'read')?.getAttribute('aria-checked')).toBe('true');
    expect(['off', 'read', 'write'].map((mode) => choice(m, mode)?.disabled)).toEqual([true, true, true]);
    expect(m.host.textContent).toContain('Only a platform admin can change it');
  });

  it('lets a platform admin change it in one click', async () => {
    const api = fakeApi(state({ can_change: true }), state({ mode: 'write', can_change: true }));
    const m = await render(api);

    expect(choice(m, 'write')?.disabled).toBe(false);
    expect(m.host.textContent).not.toContain('Only a platform admin');
    await m.click(choice(m, 'write'));
    await m.flush();
    expect(api.save).toHaveBeenCalledWith('ws1', 'write');
    expect(choice(m, 'write')?.getAttribute('aria-checked')).toBe('true');
  });

  it('keeps the mode and says why when the change is refused', async () => {
    const api = fakeApi(state({ can_change: true }), new PlatformFilesError('Only a platform admin gives it', 403));
    const m = await render(api);

    await m.click(choice(m, 'read'));
    await m.flush();
    expect(choice(m, 'off')?.getAttribute('aria-checked')).toBe('true');
    expect(m.host.textContent).toContain('Only a platform admin gives it');
  });

  it('renders nothing for someone who may not read the configuration', async () => {
    const m = await render(fakeApi(new PlatformFilesError('Forbidden', 403)));
    expect(m.host.textContent).toBe('');
  });
});

describe('createPlatformFilesApi', () => {
  it('reads and saves the workspace setting', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(state()), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(state({ mode: 'read' })), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'No' }), { status: 403 }));
    const api = createPlatformFilesApi(fetcher);

    expect((await api.read('ws 1')).mode).toBe('off');
    expect(fetcher).toHaveBeenLastCalledWith('/api/workspaces/ws%201/platform-files');
    expect((await api.save('ws1', 'read')).mode).toBe('read');
    expect(fetcher).toHaveBeenLastCalledWith('/api/workspaces/ws1/platform-files', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'read' }),
    });
    await expect(api.save('ws1', 'write')).rejects.toMatchObject({ status: 403, message: 'No' });
  });
});
