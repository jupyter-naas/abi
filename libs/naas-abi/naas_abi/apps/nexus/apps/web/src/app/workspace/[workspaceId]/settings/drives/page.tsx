'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { SettingsEmpty, SettingsNotice, SettingsPageHeader, SettingsSection } from '@/components/settings/settings-ui';
import { useWorkspaceStore } from '@/stores/workspace';

export default function DrivesSettingsPage() {
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const fetchWorkspaces = useWorkspaceStore((state) => state.fetchWorkspaces);

  const workspace = workspaces.find((w) => w.id === currentWorkspaceId) || null;
  const role = workspace?.currentUserRole;
  const canEdit = role === 'owner' || role === 'admin';

  const [savingPlatform, setSavingPlatform] = useState(false);
  const [savingSystem, setSavingSystem] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!workspace) {
    return <SettingsEmpty title="No workspace selected" />;
  }

  const platformDriveEnabled = Boolean(workspace.platformDriveEnabled);
  const systemDriveEnabled = Boolean(workspace.systemDriveEnabled);

  const handleTogglePlatform = async (next: boolean) => {
    if (!canEdit || savingPlatform) return;
    setError(null);
    setSavingPlatform(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/workspaces/${workspace.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform_drive_enabled: next }),
      });
      if (!response.ok) {
        if (response.status === 403) {
          setError('Only workspace admins can change drive settings.');
        } else {
          setError(`Failed to update setting (HTTP ${response.status}).`);
        }
        return;
      }
      await fetchWorkspaces();
    } catch (err) {
      console.error('Failed to update platform drive setting:', err);
      setError('Failed to update setting. Please try again.');
    } finally {
      setSavingPlatform(false);
    }
  };

  const handleToggleSystem = async (next: boolean) => {
    if (!canEdit || savingSystem) return;
    setError(null);
    setSavingSystem(true);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(`/api/workspaces/${workspace.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_drive_enabled: next }),
      });
      if (!response.ok) {
        if (response.status === 403) {
          setError('Only workspace admins can change drive settings.');
        } else {
          setError(`Failed to update setting (HTTP ${response.status}).`);
        }
        return;
      }
      await fetchWorkspaces();
    } catch (err) {
      console.error('Failed to update system drive setting:', err);
      setError('Failed to update setting. Please try again.');
    } finally {
      setSavingSystem(false);
    }
  };

  const driveRow = (
    title: string,
    description: string,
    checked: boolean,
    saving: boolean,
    onToggle: (next: boolean) => void
  ) => (
    <SettingsSection>
      <label className="flex cursor-pointer items-start gap-3">
        <Checkbox
          checked={checked}
          onCheckedChange={onToggle}
          disabled={!canEdit || saving}
          className="mt-0.5"
        />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">{title}</p>
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        </div>
      </label>
    </SettingsSection>
  );

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Drives"
        description="Configure which file drives are available in this workspace."
      />

      {driveRow(
        'Platform drive',
        'When enabled, members of this workspace can read and write files in the shared platform-drive tree. The platform drive is shared across every workspace that enables it.',
        platformDriveEnabled,
        savingPlatform,
        handleTogglePlatform
      )}

      {driveRow(
        'System drive',
        'When enabled, workspace owners and admins can browse the full object-storage tree. The system drive exposes all storage paths and is restricted to admin roles regardless of this setting.',
        systemDriveEnabled,
        savingSystem,
        handleToggleSystem
      )}

      {!canEdit && <SettingsNotice>Only workspace owners and admins can change drive settings.</SettingsNotice>}

      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}
    </div>
  );
}
