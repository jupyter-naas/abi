// @vitest-environment jsdom
/** The socket is not opened during a view: the server refuses its handshake (no presence, no room). */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { useAuthStore } from '@/stores/auth';

const socket = { on: vi.fn(), off: vi.fn(), emit: vi.fn(), disconnect: vi.fn(), io: { opts: {} } };
const io = vi.fn(() => socket);
vi.mock('socket.io-client', () => ({ io: (...args: unknown[]) => (io as (...a: unknown[]) => unknown)(...args) }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test', getWebsocketPath: () => '/ws/socket.io' }));

import { WebSocketProvider } from './websocket-context';

const USER = { id: 'usr_1', email: 'a@example.com', name: 'A', createdAt: new Date() };
const VIEW = {
  person: { id: 'iam_dave', name: 'Dave' },
  workspace: { id: 'ws-alpha', name: 'Alpha' },
  ends_at: new Date(Date.now() + 900_000).toISOString(),
  groups_from: null,
};

let mounted: Mounted | null = null;
beforeEach(() => {
  io.mockClear();
  socket.disconnect.mockClear();
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  useAuthStore.setState({ user: null, view: null, isAuthenticated: false });
});

const open = () => mount(WebSocketProvider, { children: createElement('div') });

describe('the WebSocket', () => {
  it('opens for a signed-in user', async () => {
    useAuthStore.setState({ user: USER, isAuthenticated: true, view: null });
    mounted = await open();
    expect(io).toHaveBeenCalledOnce();
  });

  it('is not opened during a view', async () => {
    useAuthStore.setState({ user: USER, isAuthenticated: true, view: VIEW });
    mounted = await open();
    expect(io).not.toHaveBeenCalled();
  });

  it('is closed when a view begins', async () => {
    useAuthStore.setState({ user: USER, isAuthenticated: true, view: null });
    mounted = await open();
    const { act } = await import('react');
    await act(async () => useAuthStore.setState({ view: VIEW }));
    expect(socket.disconnect).toHaveBeenCalled();
  });
});
