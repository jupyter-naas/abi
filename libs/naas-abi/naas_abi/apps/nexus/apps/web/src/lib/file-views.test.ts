import { describe, expect, it } from 'vitest';

import { fileViewsPath, hasFileView, parseFileViews } from './file-views';

const platform = {
  id: 'platform_files',
  label: 'Platform Files',
  drive: 'file_system',
  scope: 'platform_drive',
  root: 'naas_abi/platform-drive',
};
const system = {
  id: 'system_files',
  label: 'System Files',
  drive: 'file_system',
  scope: 'system_drive',
  root: '',
};

describe('fileViewsPath', () => {
  it('asks for the views of a workspace', () => {
    expect(fileViewsPath('ws-1')).toBe('/api/files/views?workspace_id=ws-1');
  });

  it('encodes the workspace id', () => {
    expect(fileViewsPath('a b')).toBe('/api/files/views?workspace_id=a%20b');
  });

  it('asks for the views of no workspace without one', () => {
    expect(fileViewsPath(null)).toBe('/api/files/views');
    expect(fileViewsPath('')).toBe('/api/files/views');
  });
});

describe('parseFileViews', () => {
  it('reads the views IAM lets the caller open, in order', () => {
    expect(parseFileViews({ views: [platform, system] })).toEqual([platform, system]);
  });

  it('keeps the root of System Files, the whole store', () => {
    expect(parseFileViews({ views: [system] })[0].root).toBe('');
  });

  it('drops entries that are not views', () => {
    expect(parseFileViews({ views: [platform, { id: 'x' }, null, 'nope'] })).toEqual([platform]);
  });

  it('reads nothing from a body that is not a listing', () => {
    expect(parseFileViews(null)).toEqual([]);
    expect(parseFileViews({})).toEqual([]);
    expect(parseFileViews({ views: 'all' })).toEqual([]);
  });
});

describe('hasFileView', () => {
  it('says whether a view is listed', () => {
    const views = parseFileViews({ views: [platform] });
    expect(hasFileView(views, 'platform_files')).toBe(true);
    expect(hasFileView(views, 'system_files')).toBe(false);
  });
});
