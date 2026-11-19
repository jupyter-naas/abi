import { describe, expect, it } from 'vitest';
import {
  driveCount,
  driveLocationText,
  driveStatusLabel,
  errorText,
  PLATFORM_DRIVES_PATH,
  type PlatformDrive,
} from './drives-model';

const FILE_SYSTEM: PlatformDrive = {
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

describe('drives model', () => {
  it('lives at /settings/drives', () => {
    expect(PLATFORM_DRIVES_PATH).toBe('/settings/drives');
  });

  it('counts drives', () => {
    expect(driveCount(1)).toBe('1 drive');
    expect(driveCount(2)).toBe('2 drives');
  });

  it('reads the location as its labelled parts', () => {
    expect(driveLocationText(FILE_SYSTEM)).toBe('bucket abi, prefix datastore');
    expect(driveLocationText({ ...FILE_SYSTEM, location: [] })).toBe('');
  });

  it('says whether the storage answers', () => {
    expect(driveStatusLabel('reachable')).toBe('Reachable');
    expect(driveStatusLabel('unreachable')).toBe('Unreachable');
  });

  it('words a refusal', () => {
    expect(errorText(403, null)).toBe('Only a platform admin can list the drives.');
    expect(errorText(500, { detail: 'boom' })).toBe('boom');
    expect(errorText(0, null)).toBe('The API did not answer.');
    expect(errorText(502, null)).toBe('The API answered 502.');
  });
});
