import { beforeEach, describe, expect, it } from 'vitest';
import { rememberWorkspacePath, workspaceReturnPath } from './workspace-return-path';

describe('workspace return path', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    Object.defineProperty(globalThis, 'window', {
      value: {
        sessionStorage: {
          getItem: (k: string) => store.get(k) ?? null,
          setItem: (k: string, v: string) => store.set(k, v),
        },
      },
      configurable: true,
    });
  });

  it('falls back until a workspace page was visited', () => {
    expect(workspaceReturnPath('/workspace/ws-1/chat', 'ws-1')).toBe('/workspace/ws-1/chat');
  });

  it('returns the last workspace page of that workspace', () => {
    rememberWorkspacePath('/workspace/ws-1/maps?layer=a');
    expect(workspaceReturnPath('/workspace/ws-1/chat', 'ws-1')).toBe('/workspace/ws-1/maps?layer=a');
    expect(workspaceReturnPath('/workspace/ws-2/chat', 'ws-2')).toBe('/workspace/ws-2/chat');
  });

  it('ignores pages outside a workspace', () => {
    rememberWorkspacePath('/settings/users');
    expect(workspaceReturnPath('/', null)).toBe('/');
  });
});
