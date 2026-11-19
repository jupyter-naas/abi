import { describe, expect, it } from 'vitest';

import {
  driveLabelForSource,
  driveRootForSource,
  filesScopeForSource,
  isRemoteDriveSource,
  relativeDrivePath,
} from './drive-label';

describe('organization drive', () => {
  it('is a drive the files API serves, with its own scope', () => {
    expect(isRemoteDriveSource('organization-drive')).toBe(true);
    expect(isRemoteDriveSource('synced-folder-1')).toBe(false);
    expect(filesScopeForSource('organization-drive')).toBe('organization_drive');
  });

  it('is rooted at the workspace organization drive', () => {
    expect(driveRootForSource('organization-drive', 'ws-1', 'u-1', 'org-1')).toBe(
      'naas_abi/organization-drive/org-1',
    );
    expect(driveRootForSource('organization-drive', 'ws-1', 'u-1')).toBe('');
  });

  it('is labelled with the organization name', () => {
    expect(driveLabelForSource('organization-drive', undefined, false, 'Acme')).toBe('Acme');
    expect(driveLabelForSource('organization-drive', undefined, false)).toBe('Organization Drive');
  });

  it('shows breadcrumbs relative to its root', () => {
    const root = driveRootForSource('organization-drive', 'ws-1', 'u-1', 'org-1');
    expect(
      relativeDrivePath('naas_abi/organization-drive/org-1/operations', root, 'organization-drive', 'ws-1'),
    ).toBe('operations');
  });
});
