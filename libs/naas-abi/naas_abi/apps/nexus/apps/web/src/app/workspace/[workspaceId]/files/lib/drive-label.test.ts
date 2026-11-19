import { describe, expect, it } from 'vitest';

import type { FileView } from '@/lib/file-views';
import {
  ALL_VIEWS,
  FILES_DRIVES,
  driveRootForSource,
  filesScopeForSource,
  filesSourceFrom,
  isFileViewSource,
  relativeDrivePath,
  sourceForFileView,
  viewChoices,
  viewFolders,
  viewLabel,
  viewsOfDrive,
} from './drive-label';

const view = (id: FileView['id'], label: string, scope: string, root: string): FileView => ({
  id,
  label,
  drive: 'file_system',
  scope,
  root,
});

const VIEWS: FileView[] = [
  view('my_files', 'My Files', 'my_drive', 'naas_abi/my-drive/u-1'),
  view('workspace_files', 'Workspace Files', 'workspace', 'naas_abi/workspace-drive/ws-1'),
  view('organization_files', 'Organization Files', 'organization_drive', 'naas_abi/organization-drive/org-1'),
  view('platform_files', 'Platform Files', 'platform_drive', 'naas_abi/platform-drive'),
];

describe('the views of the file system', () => {
  it('map each view to the files API scope, which does not change', () => {
    expect(filesScopeForSource('my-files')).toBe('my_drive');
    expect(filesScopeForSource('workspace-files')).toBe('workspace');
    expect(filesScopeForSource('organization-files')).toBe('organization_drive');
    expect(filesScopeForSource('platform-files')).toBe('platform_drive');
    expect(filesScopeForSource('system-files')).toBe('system_drive');
  });

  it('All Views is no scope: nothing is listed from the API for it', () => {
    expect(filesScopeForSource(ALL_VIEWS)).toBeNull();
    expect(isFileViewSource(ALL_VIEWS)).toBe(false);
    expect(isFileViewSource('my-files')).toBe(true);
    expect(driveRootForSource(ALL_VIEWS, 'ws-1', 'u-1', 'org-1')).toBe('');
  });

  it('are labelled by view, never as a drive, and Organization Files not by the organization', () => {
    expect(viewLabel(ALL_VIEWS)).toBe('All Views');
    expect(viewLabel('my-files')).toBe('My Files');
    expect(viewLabel('workspace-files')).toBe('Workspace Files');
    expect(viewLabel('organization-files')).toBe('Organization Files');
    expect(viewLabel('platform-files')).toBe('Platform Files');
    expect(viewLabel('system-files')).toBe('System Files');
  });

  it('are rooted where the storage keeps them', () => {
    expect(driveRootForSource('my-files', 'ws-1', 'u-1')).toBe('naas_abi/my-drive/u-1');
    expect(driveRootForSource('workspace-files', 'ws-1')).toBe('naas_abi/workspace-drive/ws-1');
    expect(driveRootForSource('organization-files', 'ws-1', 'u-1', 'org-1')).toBe(
      'naas_abi/organization-drive/org-1',
    );
    expect(driveRootForSource('organization-files', 'ws-1', 'u-1')).toBe('');
    expect(driveRootForSource('platform-files', 'ws-1')).toBe('naas_abi/platform-drive');
    expect(driveRootForSource('system-files', 'ws-1')).toBe('');
  });

  it('show breadcrumbs relative to their root', () => {
    const root = driveRootForSource('organization-files', 'ws-1', 'u-1', 'org-1');
    expect(
      relativeDrivePath('naas_abi/organization-drive/org-1/operations', root, 'organization-files', 'ws-1'),
    ).toBe('operations');
    expect(relativeDrivePath('ws-1/docs', 'naas_abi/workspace-drive/ws-1', 'workspace-files', 'ws-1')).toBe(
      'docs',
    );
  });

  it('match the ids GET /api/files/views answers', () => {
    expect(sourceForFileView('my_files')).toBe('my-files');
    expect(sourceForFileView('workspace_files')).toBe('workspace-files');
    expect(sourceForFileView('organization_files')).toBe('organization-files');
    expect(sourceForFileView('platform_files')).toBe('platform-files');
    expect(sourceForFileView('system_files')).toBe('system-files');
  });
});

describe('old sources (deep links, starred items) open the right view', () => {
  it.each([
    ['my-drive', 'my-files'],
    ['workspace', 'workspace-files'],
    ['organization-drive', 'organization-files'],
    ['platform-drive', 'platform-files'],
    ['system-drive', 'system-files'],
  ])('%s opens %s', (old, current) => {
    expect(filesSourceFrom(old)).toBe(current);
  });

  it('keeps the new sources and the API view ids, and knows nothing else', () => {
    expect(filesSourceFrom('platform-files')).toBe('platform-files');
    expect(filesSourceFrom('all')).toBe('all');
    expect(filesSourceFrom('my_files')).toBe('my-files');
    expect(filesSourceFrom(' system-files ')).toBe('system-files');
    expect(filesSourceFrom('synced-1700000000')).toBeNull();
    expect(filesSourceFrom('')).toBeNull();
    expect(filesSourceFrom(null)).toBeNull();
  });
});

describe('the Drive and View dropdowns', () => {
  it('offer All Drives, then File System', () => {
    expect(FILES_DRIVES.map((d) => d.label)).toEqual(['All Drives', 'File System']);
  });

  it('list the same views under All Drives and File System (one drive today)', () => {
    expect(viewsOfDrive(VIEWS, 'all')).toEqual(VIEWS);
    expect(viewsOfDrive(VIEWS, 'file_system')).toEqual(VIEWS);
    expect(viewsOfDrive([{ ...VIEWS[0], drive: 'google_drive' }], 'file_system')).toEqual([]);
  });

  it('offer All Views first, then only the views the caller may open, in order', () => {
    expect(viewChoices(VIEWS, 'all')).toEqual([
      { value: 'all', label: 'All Views' },
      { value: 'my-files', label: 'My Files' },
      { value: 'workspace-files', label: 'Workspace Files' },
      { value: 'organization-files', label: 'Organization Files' },
      { value: 'platform-files', label: 'Platform Files' },
    ]);
    expect(viewChoices([VIEWS[1]], 'all').map((c) => c.value)).toEqual(['all', 'workspace-files']);
    expect(viewChoices([], 'all').map((c) => c.value)).toEqual(['all']);
  });
});

describe('All Views', () => {
  it('is one folder per view the caller may open, each opening into its view', () => {
    expect(viewFolders(VIEWS, 'all')).toEqual([
      { source: 'my-files', label: 'My Files' },
      { source: 'workspace-files', label: 'Workspace Files' },
      { source: 'organization-files', label: 'Organization Files' },
      { source: 'platform-files', label: 'Platform Files' },
    ]);
  });

  it('lists no folder for a view the caller may not open', () => {
    expect(viewFolders([VIEWS[0], VIEWS[1]], 'all').map((f) => f.source)).toEqual([
      'my-files',
      'workspace-files',
    ]);
  });
});
