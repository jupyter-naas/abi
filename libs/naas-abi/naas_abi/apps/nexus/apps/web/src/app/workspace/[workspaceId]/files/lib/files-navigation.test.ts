import { describe, expect, it } from 'vitest';
import { listOnSourceChange, startNavigation } from './files-navigation';

describe('startNavigation', () => {
  // A sidebar tree click in the open view changes no source: nothing would list it later.
  it('lists the folder now when the view does not change', () => {
    expect(startNavigation('my-files', 'my-files', 'documents')).toEqual({ listNow: 'documents', pending: null });
  });

  it('waits for the view to open when it changes', () => {
    expect(startNavigation('all', 'my-files', 'documents')).toEqual({
      listNow: null,
      pending: { source: 'my-files', path: 'documents' },
    });
  });
});

describe('listOnSourceChange', () => {
  it('lists the root of a view chosen with nothing pending', () => {
    expect(listOnSourceChange(null, 'workspace-files', 'workspace-files')).toEqual({ list: '', pending: null });
  });

  // Was: a tree click left a skip flag set, so the next view change listed nothing and
  // the page showed My Files/documents under "Workspace Files".
  it('lists the new view root after a same-view navigation (nothing left pending)', () => {
    const { pending } = startNavigation('my-files', 'my-files', 'documents');
    expect(listOnSourceChange(pending, 'workspace-files', 'workspace-files')).toEqual({ list: '', pending: null });
  });

  it('lists the navigation folder once its view is the rendered one', () => {
    const pending = { source: 'my-files' as const, path: 'documents' };
    expect(listOnSourceChange(pending, 'my-files', 'my-files')).toEqual({ list: 'documents', pending: null });
  });

  // Was: a deep link in a fresh tab opened the view root (the mount run used the flag).
  it('waits while the render is behind the store (fresh tab deep link)', () => {
    const pending = { source: 'my-files' as const, path: 'documents' };
    expect(listOnSourceChange(pending, 'all', 'my-files')).toEqual({ list: null, pending });
  });

  it('drops a navigation another change overrode (fallback to All Views)', () => {
    const pending = { source: 'system-files' as const, path: 'x' };
    expect(listOnSourceChange(pending, 'all', 'all')).toEqual({ list: '', pending: null });
  });
});
