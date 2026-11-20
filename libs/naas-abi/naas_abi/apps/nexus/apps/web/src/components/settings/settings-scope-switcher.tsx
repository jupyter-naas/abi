'use client';

import { useId, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Building2, Check, ChevronsUpDown, Layers, Search, type LucideIcon } from 'lucide-react';
import { useDismiss } from '@/hooks/use-dismiss';
import { useOpenableOrganizations } from '@/hooks/use-openable-organizations';
import { cn } from '@/lib/utils';
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

/** A level picked from a list with a search box: its kind over its name, as the trigger. */
function ScopeDropdown({
  kind,
  icon: Icon,
  value,
  options,
  onPick,
}: {
  kind: 'Organization' | 'Workspace';
  icon: LucideIcon;
  value: string;
  options: Option[];
  onPick: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const { ref, triggerRef } = useDismiss(open, setOpen);
  const panelId = useId();
  const noun = kind.toLowerCase();
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;
  }, [options, query]);
  const current = options.find((o) => o.id === value)?.label ?? value;

  const pick = (id: string) => {
    setOpen(false);
    setQuery('');
    if (id !== value) onPick(id);
  };

  return (
    <div ref={ref} className="settings-scope-switcher" data-scope-switcher={noun}>
      <button
        ref={triggerRef}
        type="button"
        className="settings-scope-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        title={`Switch ${noun}`}
      >
        <Icon size={14} className="settings-scope-icon" aria-hidden="true" />
        <span className="settings-scope-text">
          <span className="settings-scope-kind">{kind}</span>
          <span className="settings-scope-name">{current}</span>
        </span>
        <ChevronsUpDown size={14} className="settings-scope-icon" aria-hidden="true" />
      </button>
      {open && (
        <div id={panelId} role="dialog" aria-label={`Switch ${noun}`} className="settings-scope-panel">
          <label className="settings-scope-search">
            <Search size={13} aria-hidden="true" />
            <input
              autoFocus
              type="search"
              aria-label={`Search ${noun}s`}
              placeholder={`Search ${noun}s…`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && shown.length > 0) pick(shown[0].id);
              }}
            />
          </label>
          <ul className="settings-scope-options">
            {shown.length === 0 && <li className="settings-scope-empty">No {noun}s match.</li>}
            {shown.map((o) => (
              <li key={o.id}>
                <button
                  type="button"
                  className={cn('settings-scope-option', o.id === value && 'is-current')}
                  data-option={o.id}
                  onClick={() => pick(o.id)}
                >
                  <span className="settings-scope-option-label">{o.label}</span>
                  {o.id === value && <Check size={14} aria-label="Current" />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
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
      <div className="settings-scope">
        {org && (
          <ScopeDropdown
            kind="Organization"
            icon={Building2}
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
          icon={Layers}
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
      <div className="settings-scope">
        <ScopeDropdown
          kind="Organization"
          icon={Building2}
          value={orgId}
          options={options}
          onPick={(id) => router.push(organizationSettingsSwitchPath(pathname, id))}
        />
      </div>
    );
  }
  return null;
}
