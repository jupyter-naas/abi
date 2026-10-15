import { describe, expect, it } from 'vitest';

import { isSystemFileName, isSystemPath, withoutSystemFiles } from './system-files';

describe('isSystemFileName', () => {
  it('flags dot names', () => {
    expect(isSystemFileName('.gitkeep')).toBe(true);
    expect(isSystemFileName('.abi')).toBe(true);
  });

  it('leaves ordinary names alone, dots inside included', () => {
    expect(isSystemFileName('README.md')).toBe(false);
    expect(isSystemFileName('archive.tar.gz')).toBe(false);
  });
});

describe('isSystemPath', () => {
  it('flags a path with a system segment anywhere', () => {
    expect(isSystemPath('.abi')).toBe(true);
    expect(isSystemPath('docs/.abi/config.yaml')).toBe(true);
    expect(isSystemPath('docs/notes/.env')).toBe(true);
  });

  it('ignores empty segments from leading or doubled slashes', () => {
    expect(isSystemPath('/docs//notes/a.txt')).toBe(false);
    expect(isSystemPath('')).toBe(false);
  });
});

describe('withoutSystemFiles', () => {
  const files = [{ name: '.gitkeep' }, { name: 'a.txt' }, { name: '.abi' }];

  it('hides system entries by default', () => {
    expect(withoutSystemFiles(files, false)).toEqual([{ name: 'a.txt' }]);
  });

  it('keeps everything when asked to show them', () => {
    expect(withoutSystemFiles(files, true)).toBe(files);
  });
});
