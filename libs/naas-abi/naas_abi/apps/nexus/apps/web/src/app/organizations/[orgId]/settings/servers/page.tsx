'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ServersPanel } from '@/components/settings/servers-panel';
import { SettingsFilterSelect, SettingsLoading, SettingsNotice } from '@/components/settings/settings-ui';
import { authFetch } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';
import { orgSettingsSectionPath } from '../lib/nav';

interface OrgWorkspace {
  id: string;
  name: string;
}

/**
 * Organization Settings > Servers. Servers are stored per workspace: pick one of
 * the organization's workspaces (``?workspace=<id>``, else the current one).
 */
export default function OrgServersPage() {
  const orgId = useParams()?.orgId as string;
  const router = useRouter();
  const searchParams = useSearchParams();
  const requested = searchParams?.get('workspace') ?? null;
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(`/api/organizations/${orgId}/workspaces`);
        if (cancelled) return;
        if (!res.ok) {
          setError(`Failed to load the workspaces (HTTP ${res.status}).`);
          setWorkspaces([]);
          return;
        }
        const data: OrgWorkspace[] = await res.json();
        setWorkspaces([...data].sort((a, b) => a.name.localeCompare(b.name)));
      } catch {
        if (!cancelled) {
          setError('Failed to load the workspaces.');
          setWorkspaces([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const selectedId = useMemo(() => {
    if (!workspaces || workspaces.length === 0) return null;
    const ids = new Set(workspaces.map((workspace) => workspace.id));
    if (requested && ids.has(requested)) return requested;
    if (currentWorkspaceId && ids.has(currentWorkspaceId)) return currentWorkspaceId;
    return workspaces[0].id;
  }, [workspaces, requested, currentWorkspaceId]);

  if (workspaces === null) return <SettingsLoading />;
  if (!selectedId) {
    return <SettingsNotice tone="error">{error || 'No workspace in this organization.'}</SettingsNotice>;
  }

  return (
    <ServersPanel
      workspaceId={selectedId}
      workspacePicker={
        <SettingsFilterSelect
          label="Workspace"
          value={selectedId}
          onChange={(id) =>
            router.replace(`${orgSettingsSectionPath(orgId, 'servers')}?workspace=${encodeURIComponent(id)}`)
          }
          options={workspaces.map((workspace) => ({ value: workspace.id, label: workspace.name }))}
        />
      }
    />
  );
}
