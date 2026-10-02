'use client';

import { useState } from 'react';
import { Folder, HardDrive, Loader2, Server, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import {
  SettingsEmpty,
  SettingsFilterSelect,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  countLabel,
  settingsTable,
} from '@/components/settings/settings-ui';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';

type DriveFlag = 'platform_drive_enabled' | 'system_drive_enabled';

type DriveRow = {
  id: string;
  name: string;
  icon: LucideIcon;
  description: string;
  access: string;
  enabled: boolean;
  /** Set for drives an admin can turn on. Drives are never turned off from here. */
  flag?: DriveFlag;
};

/**
 * The drives of this workspace, the same set the Files sidebar shows. Enabled drives
 * cannot be disabled from here; owners and admins can turn on a drive that is off.
 */
export default function DrivesSettingsPage() {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const syncedFolders = useFilesStore((state) => state.syncedFolders);
  const { confirm: confirmTurnOn, dialog: confirmDialog } = useConfirm();

  const [searchQuery, setSearchQuery] = useState('');
  const [accessFilter, setAccessFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [turningOn, setTurningOn] = useState<DriveFlag | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!workspace) {
    return <SettingsEmpty title="No workspace selected" />;
  }

  const isWorkspaceAdmin = workspace.currentUserRole === 'owner' || workspace.currentUserRole === 'admin';
  const platformOn = Boolean(workspace.platformDriveEnabled);
  const systemOn = Boolean(workspace.systemDriveEnabled);

  // Same rules as the Drives list in the Files sidebar, plus the drives an admin can still turn on.
  const drives: DriveRow[] = [
    {
      id: 'my-drive',
      name: 'My Drive',
      icon: HardDrive,
      description: 'Your personal files in this workspace.',
      access: 'Only you',
      enabled: true,
    },
    {
      id: 'workspace',
      name: 'Workspace Drive',
      icon: HardDrive,
      description: 'Files shared with every member of this workspace.',
      access: 'All members',
      enabled: true,
    },
    ...(platformOn || isWorkspaceAdmin
      ? [
          {
            id: 'platform-drive',
            name: 'Platform Drive',
            icon: HardDrive,
            description: 'Files shared across every workspace where the platform drive is enabled.',
            access: 'All members',
            enabled: platformOn,
            flag: 'platform_drive_enabled' as const,
          },
        ]
      : []),
    ...(isWorkspaceAdmin
      ? [
          {
            id: 'system-drive',
            name: 'System Drive',
            icon: Server,
            description: 'Full object-storage tree, visible to workspace owners and admins.',
            access: 'Owners & admins',
            enabled: systemOn,
            flag: 'system_drive_enabled' as const,
          },
        ]
      : []),
    ...syncedFolders.map((folder) => ({
      id: folder.id,
      name: folder.name,
      icon: Folder,
      description: `Synced folder · ${folder.localPath}`,
      access: 'This browser',
      enabled: true,
    })),
  ];
  const enabledCount = drives.filter((drive) => drive.enabled).length;
  const accessOptions = Array.from(new Set(drives.map((drive) => drive.access)));
  const query = searchQuery.trim().toLowerCase();
  const filteredDrives = drives.filter((drive) => {
    if (accessFilter !== 'all' && drive.access !== accessFilter) return false;
    if (statusFilter === 'enabled' && !drive.enabled) return false;
    if (statusFilter === 'off' && drive.enabled) return false;
    return !query || `${drive.name} ${drive.description}`.toLowerCase().includes(query);
  });

  const turnOn = async (drive: DriveRow) => {
    if (!drive.flag || !isWorkspaceAdmin || turningOn) return;
    const ok = await confirmTurnOn({
      title: `Turn on ${drive.name}?`,
      description: `${drive.description}\n\nOnce on, it cannot be turned off from Settings.`,
      confirmLabel: 'Turn on',
      destructive: false,
    });
    if (!ok) return;
    setError(null);
    setTurningOn(drive.flag);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/workspaces/${workspace.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [drive.flag]: true }),
      });
      if (!response.ok) {
        setError(
          response.status === 403
            ? 'Only workspace admins can turn on drives.'
            : `Failed to turn on ${drive.name} (HTTP ${response.status}).`
        );
        return;
      }
      await fetchWorkspaces();
    } catch (err) {
      console.error(`Failed to turn on ${drive.name}:`, err);
      setError(`Failed to turn on ${drive.name}. Please try again.`);
    } finally {
      setTurningOn(null);
    }
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Drives"
        badge={`${enabledCount} enabled`}
        description={
          isWorkspaceAdmin
            ? 'File drives of this workspace. Enabled drives stay on; drives that are off can be turned on.'
            : 'File drives enabled in this workspace.'
        }
      />

      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}

      <div className="space-y-4">
        <SettingsTableToolbar
          search={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search drives..."
          filters={
            <>
              <SettingsFilterSelect
                label="Access"
                value={accessFilter}
                onChange={setAccessFilter}
                options={[
                  { value: 'all', label: 'All access' },
                  ...accessOptions.map((access) => ({ value: access, label: access })),
                ]}
              />
              <SettingsFilterSelect
                label="Status"
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  { value: 'all', label: 'All statuses' },
                  { value: 'enabled', label: 'Enabled' },
                  { value: 'off', label: 'Off' },
                ]}
              />
            </>
          }
          meta={`${countLabel(filteredDrives.length, drives.length, 'drive')} · ${enabledCount} enabled`}
        />
        <div className={settingsTable.wrapper}>
          <table className={settingsTable.table}>
            <thead>
              <tr className={settingsTable.headRow}>
                <th className={settingsTable.th}>Drive</th>
                <th className={cn(settingsTable.th, 'w-40')}>Access</th>
                <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {filteredDrives.length === 0 && (
                <tr>
                  <td colSpan={3} className="p-8 text-center text-muted-foreground">
                    No drives match the current search and filters
                  </td>
                </tr>
              )}
              {filteredDrives.map((drive) => {
                const Icon = drive.icon;
                const busy = turningOn !== null && turningOn === drive.flag;
                return (
                  <tr key={drive.id} className={settingsTable.row}>
                    <td className={settingsTable.td}>
                      <div className="flex items-start gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-muted">
                          <Icon size={16} className="text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className={cn('font-medium', !drive.enabled && 'text-muted-foreground')}>{drive.name}</p>
                          <p className="text-xs text-muted-foreground">{drive.description}</p>
                        </div>
                      </div>
                    </td>
                    <td className={settingsTable.td}>
                      <Badge variant="outline">{drive.access}</Badge>
                    </td>
                    <td className={settingsTable.td}>
                      {/* Enabled drives stay on (checked, locked); admins can tick a drive that is off. */}
                      <span className="inline-flex items-center gap-2">
                        <Checkbox
                          checked={drive.enabled}
                          onCheckedChange={(checked) => {
                            if (checked) void turnOn(drive);
                          }}
                          disabled={drive.enabled || !drive.flag || !isWorkspaceAdmin || turningOn !== null}
                          aria-label={`${drive.name} enabled`}
                          title={drive.enabled ? `${drive.name} is enabled and stays on` : `Turn on ${drive.name}`}
                        />
                        {busy && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      {confirmDialog}
    </div>
  );
}
