import { describe, expect, it } from 'vitest';

import { resolveShellTitle } from './shell-title-entry';

describe('resolveShellTitle', () => {
  it('uses the title the current page registered', () => {
    expect(
      resolveShellTitle({ title: 'Marketplace', pathname: '/workspace/ws-1/marketplace' }, '/workspace/ws-1/marketplace')
    ).toEqual({ title: 'Marketplace', subtitle: undefined });
  });

  it('carries the subtitle through', () => {
    expect(
      resolveShellTitle(
        { title: 'Files', subtitle: 'Synced from your machine', pathname: '/workspace/ws-1/files' },
        '/workspace/ws-1/files'
      )
    ).toEqual({ title: 'Files', subtitle: 'Synced from your machine' });
  });

  it('drops a title belonging to the route we just left', () => {
    // Pages that render no Header (platform admin) would otherwise keep showing
    // the previous page's name in the mobile top bar.
    expect(
      resolveShellTitle({ title: 'Files', pathname: '/workspace/ws-1/files' }, '/workspace/ws-1/admin/events')
    ).toEqual({});
  });

  it('has nothing to say before any page has registered', () => {
    expect(resolveShellTitle(null, '/workspace/ws-1/chat')).toEqual({});
  });

  it('holds back until the pathname is known', () => {
    expect(
      resolveShellTitle({ title: 'Chat', pathname: '/workspace/ws-1/chat' }, null)
    ).toEqual({});
  });
});
