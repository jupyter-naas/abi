export type DriveFlag = 'platform_drive_enabled' | 'system_drive_enabled';

export type DriveIcon = 'drive' | 'server' | 'folder';

export type DriveRow = {
  id: string;
  name: string;
  icon: DriveIcon;
  description: string;
  access: string;
  enabled: boolean;
  /** Set for the drives a workspace flag controls. */
  flag?: DriveFlag;
  /** True when the viewer can turn this drive on or off. */
  toggleable: boolean;
};

export type DriveViewer = {
  role: string | null | undefined;
  isSuperadmin: boolean;
};

export type SyncedFolder = { id: string; name: string; localPath: string };

/** Only a platform superadmin can turn the platform and system drives on or off. */
export function canToggleDrives(viewer: DriveViewer): boolean {
  return viewer.isSuperadmin;
}

/**
 * The drives of a workspace, the same set the Files sidebar shows. My Drive, Workspace Drive and
 * synced folders are always on. The platform and system drives follow a workspace flag that only a
 * platform superadmin can change; owners, admins and superadmins can see them while they are off.
 */
export function buildDriveRows({
  viewer,
  platformOn,
  systemOn,
  syncedFolders,
}: {
  viewer: DriveViewer;
  platformOn: boolean;
  systemOn: boolean;
  syncedFolders: SyncedFolder[];
}): DriveRow[] {
  const isWorkspaceAdmin = viewer.role === 'owner' || viewer.role === 'admin';
  const canSeeOffDrives = isWorkspaceAdmin || viewer.isSuperadmin;
  const toggleable = canToggleDrives(viewer);

  return [
    {
      id: 'my-drive',
      name: 'My Drive',
      icon: 'drive',
      description: 'Your personal files in this workspace.',
      access: 'Only you',
      enabled: true,
      toggleable: false,
    },
    {
      id: 'workspace',
      name: 'Workspace Drive',
      icon: 'drive',
      description: 'Files shared with every member of this workspace.',
      access: 'All members',
      enabled: true,
      toggleable: false,
    },
    ...(platformOn || canSeeOffDrives
      ? [
          {
            id: 'platform-drive',
            name: 'Platform Drive',
            icon: 'drive' as const,
            description: 'Files shared across every workspace where the platform drive is enabled.',
            access: 'All members',
            enabled: platformOn,
            flag: 'platform_drive_enabled' as const,
            toggleable,
          },
        ]
      : []),
    ...(canSeeOffDrives
      ? [
          {
            id: 'system-drive',
            name: 'System Drive',
            icon: 'server' as const,
            description: 'Full object-storage tree, visible to workspace owners and admins.',
            access: 'Owners & admins',
            enabled: systemOn,
            flag: 'system_drive_enabled' as const,
            toggleable,
          },
        ]
      : []),
    ...syncedFolders.map((folder) => ({
      id: folder.id,
      name: folder.name,
      icon: 'folder' as const,
      description: `Synced folder · ${folder.localPath}`,
      access: 'This browser',
      enabled: true,
      toggleable: false,
    })),
  ];
}
