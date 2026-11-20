'use client';

import { useMemo } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { SearchPicker } from '@/components/shell/sidebar/search-picker';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { useWorkspaceStore, type Workspace } from '@/stores/workspace';
import {
  organizationSettingsSwitchPath,
  organizationsOfWorkspaces,
  settingsOrganizationId,
  settingsWorkspaceId,
  workspaceSettingsSwitchPath,
} from './settings-scope-switch';

type Option = { id: string; label: string };

const NONE: Workspace[] = [];

/** A level picked as Files picks a drive (its single-choice picker, with a search box), under
 *  its kind. */
function ScopeDropdown({
  kind,
  value,
  options,
  onPick,
}: {
  kind: 'Organization' | 'Workspace';
  value: string;
  options: Option[];
  onPick: (id: string) => void;
}) {
  const noun = kind.toLowerCase();
  const current = options.find((o) => o.id === value)?.label ?? value;
  return (
    <div className="settings-scope-switcher" data-scope-switcher={noun}>
      <span className="settings-scope-kind" aria-hidden="true">
        {kind}
      </span>
      <SearchPicker
        single
        ariaLabel={`Switch ${noun}`}
        items={options.map((o) => ({ value: o.id, label: o.label }))}
        value={[value]}
        onToggle={(id) => {
          if (id !== value) onPick(id);
        }}
        onClear={() => undefined}
        loading={false}
        error={null}
        label={current}
        noun={`${noun}s`}
      />
    </div>
  );
}

/**
 * Atop the Settings column of an organization or a workspace: the organization, and in a
 * workspace's Settings its workspace, each switched from a list with a search box. Picking
 * one keeps the section open (Users stays Users). In a workspace's Settings the organization
 * lists those of the caller's workspaces, and picking one opens its first workspace.
 */
export function SettingsScopeSwitcher() {
  const pathname = usePathname() ?? '';
  const router = useRouter();
  const workspaces = useWorkspaceStore((s) => s.workspaces) ?? NONE;
  const setCurrentWorkspace = useWorkspaceStore((s) => s.setCurrentWorkspace);
  const { orgs: openable } = useOpenableOrganizations();
  const workspaceId = settingsWorkspaceId(pathname);
  const orgId = settingsOrganizationId(pathname);
  const byWorkspace = useMemo(() => organizationsOfWorkspaces(workspaces), [workspaces]);

  if (workspaceId) {
    const workspace = workspaces.find((w) => w.id === workspaceId);
    if (!workspace) return null;
    const org = byWorkspace.find((o) => o.id === workspace.organizationId);
    const siblings = org?.workspaces ?? [workspace];
    const open = (id: string) => {
      setCurrentWorkspace(id);
      router.push(workspaceSettingsSwitchPath(pathname, id));
    };
    return (
      <div className="settings-scope search-picker-stack">
        {org && (
          <ScopeDropdown
            kind="Organization"
            value={org.id}
            options={byWorkspace.map((o) => ({ id: o.id, label: o.name }))}
            onPick={(id) => {
              const first = byWorkspace.find((o) => o.id === id)?.workspaces[0];
              if (first) open(first.id);
            }}
          />
        )}
        <ScopeDropdown
          kind="Workspace"
          value={workspace.id}
          options={siblings.map((w) => ({ id: w.id, label: w.name }))}
          onPick={open}
        />
      </div>
    );
  }

  if (orgId) {
    const options = [...openable]
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((o) => ({ id: o.id, label: o.name }));
    if (!options.some((o) => o.id === orgId)) return null;
    return (
      <div className="settings-scope search-picker-stack">
        <ScopeDropdown
          kind="Organization"
          value={orgId}
          options={options}
          onPick={(id) => router.push(organizationSettingsSwitchPath(pathname, id))}
        />
      </div>
    );
  }
  return null;
}
