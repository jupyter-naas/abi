import { describe, expect, it } from 'vitest';

import { resolveMobileTopBarTitle } from './mobile-top-bar-title';

describe('resolveMobileTopBarTitle', () => {
  it('uses shell override on list tabs', () => {
    expect(
      resolveMobileTopBarTitle({
        variant: 'top',
        titleOverride: 'Files',
        pageTitle: 'Workspace Drive',
        workspaceName: 'Acme',
      })
    ).toBe('Files');
  });

  it('uses the conversation title on chat thread detail', () => {
    expect(
      resolveMobileTopBarTitle({
        variant: 'detail',
        pageTitle: 'Chat',
        threadTitle: 'Quarterly plan',
        isChatThread: true,
      })
    ).toBe('Quarterly plan');
  });

  it('uses the page-registered drive name on files browse detail', () => {
    expect(
      resolveMobileTopBarTitle({
        variant: 'detail',
        pageTitle: 'Workspace Drive',
        threadTitle: 'New chat',
        isChatThread: false,
      })
    ).toBe('Workspace Drive');
  });

  it('does not fall back to stale chat titles on files browse detail', () => {
    expect(
      resolveMobileTopBarTitle({
        variant: 'detail',
        threadTitle: 'New chat',
        isChatThread: false,
      })
    ).toBe('');
  });
});
