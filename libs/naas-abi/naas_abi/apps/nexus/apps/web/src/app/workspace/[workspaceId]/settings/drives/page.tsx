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
import { useAuthStore } from '@/stores/auth';
import { useFilesStore } from '@/stores/files';
import { useWorkspaceStore } from '@/stores/workspace';
import { buildDriveRows, canToggleDrives, type DriveFlag, type DriveIcon, type DriveRow } from './drive-rows';

const DRIVE_ICONS: Record<DriveIcon, LucideIcon> = {
  drive: HardDrive,
  server: Server,
  folder: Folder,
};

const SUPERADMIN_ONLY = 'Only a platform superadmin can turn drives on or off.';

/**
 * The drives of this workspace, the same set the Files sidebar shows. The platform and system
 * drives can be turned on and off by a platform superadmin only; everyone else sees the table
 * read-only.
 */
export default function DrivesSettingsPage() {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);
  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const syncedFolders = useFilesStore((state) => state.syncedFolders);
  const isSuperadmin = useAuthStore((state) => !!state.user?.is_superadmin);
  const { confirm: confirmToggle, dialog: confirmDialog } = useConfirm();

  const [searchQuery, setSearchQuery] = useState('');
  const [accessFilter, setAccessFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [updating, setUpdating] = useState<DriveFlag | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!workspace) {
    return <SettingsEmpty title="No workspace selected" />;
  }

  const viewer = { role: workspace.currentUserRole, isSuperadmin };
  const canToggle = canToggleDrives(viewer);
  const drives = buildDriveRows({
    viewer,
    platformOn: Boolean(workspace.platformDriveEnabled),
    systemOn: Boolean(workspace.systemDriveEnabled),
    syncedFolders,
  });
  const enabledCount = drives.filter((drive) => drive.enabled).length;
  const accessOptions = Array.from(new Set(drives.map((drive) => drive.access)));
  const query = searchQuery.trim().toLowerCase();
  const filteredDrives = drives.filter((drive) => {
    if (accessFilter !== 'all' && drive.access !== accessFilter) return false;
    if (statusFilter === 'enabled' && !drive.enabled) return false;
    if (statusFilter === 'off' && drive.enabled) return false;
    return !query || `${drive.name} ${drive.description}`.toLowerCase().includes(query);
  });

  const setDrive = async (drive: DriveRow, checked: boolean) => {
    if (!drive.flag || !drive.toggleable || updating) return;
    const verb = checked ? 'on' : 'off';
    const ok = await confirmToggle(
      checked
        ? {
            title: `Turn on ${drive.name}?`,
            description: drive.description,
            confirmLabel: 'Turn on',
            destructive: false,
          }
        : {
            title: `Turn off ${drive.name}?`,
            description: `Members of this workspace lose access to ${drive.name}. Its files stay in storage.`,
            confirmLabel: 'Turn off',
            destructive: true,
          }
    );
    if (!ok) return;
    setError(null);
    setUpdating(drive.flag);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/workspaces/${workspace.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [drive.flag]: checked }),
      });
      if (!response.ok) {
        setError(
          response.status === 403
            ? SUPERADMIN_ONLY
            : `Failed to turn ${verb} ${drive.name} (HTTP ${response.status}).`
        );
        return;
      }
      await fetchWorkspaces();
    } catch (err) {
      console.error(`Failed to turn ${verb} ${drive.name}:`, err);
      setError(`Failed to turn ${verb} ${drive.name}. Please try again.`);
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Drives"
        badge={`${enabledCount} enabled`}
        description={
          canToggle
            ? 'File drives of this workspace. As a platform superadmin you can turn the platform and system drives on or off.'
            : 'File drives enabled in this workspace.'
        }
      />

      {!canToggle && <SettingsNotice>{SUPERADMIN_ONLY}</SettingsNotice>}

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
                const Icon = DRIVE_ICONS[drive.icon];
                const busy = updating !== null && updating === drive.flag;
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
                      {/* Locked drives are always on. Only a superadmin can tick or untick the others. */}
                      <span className="inline-flex items-center gap-2">
                        <Checkbox
                          checked={drive.enabled}
                          onCheckedChange={(checked) => void setDrive(drive, checked === true)}
                          disabled={!drive.toggleable || updating !== null}
                          aria-label={`${drive.name} enabled`}
                          title={
                            !drive.flag
                              ? `${drive.name} is always enabled`
                              : drive.toggleable
                                ? drive.enabled
                                  ? `Turn off ${drive.name}`
                                  : `Turn on ${drive.name}`
                                : SUPERADMIN_ONLY
                          }
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
