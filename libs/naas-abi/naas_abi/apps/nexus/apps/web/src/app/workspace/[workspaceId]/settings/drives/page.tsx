'use client';

import { useState } from 'react';
import { HardDrive, Loader2 } from 'lucide-react';
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
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">No workspace selected</p>
      </div>
    );
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

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <HardDrive className="h-5 w-5 text-workspace-accent" />
          <h1 className="text-xl font-semibold">Drives</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Configure which file drives are available in this workspace.
        </p>
      </header>

      <section className="rounded-lg border bg-card p-4">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={platformDriveEnabled}
            onChange={(e) => handleTogglePlatform(e.target.checked)}
            disabled={!canEdit || savingPlatform}
            className="mt-1 h-4 w-4 rounded border-input"
          />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium">Platform drive</p>
              {savingPlatform && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              When enabled, members of this workspace can read and write files in the
              shared platform-drive tree. The platform drive is shared across every
              workspace that enables it.
            </p>
          </div>
        </label>
      </section>

      <section className="rounded-lg border bg-card p-4">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={systemDriveEnabled}
            onChange={(e) => handleToggleSystem(e.target.checked)}
            disabled={!canEdit || savingSystem}
            className="mt-1 h-4 w-4 rounded border-input"
          />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium">System drive</p>
              {savingSystem && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              When enabled, workspace owners and admins can browse the full
              object-storage tree. The system drive exposes all storage paths and
              is restricted to admin roles regardless of this setting.
            </p>
          </div>
        </label>
      </section>

      {!canEdit && (
        <p className="text-xs text-muted-foreground">
          Only workspace owners and admins can change drive settings.
        </p>
      )}

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
