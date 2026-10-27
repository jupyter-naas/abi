'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Download,
  Blocks,
  ExternalLink,
  Filter,
  FolderKanban,
  Pencil,
  Plus,
} from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { Checkbox } from '@/components/ui/checkbox';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { SearchBox } from '@/components/settings/search-box';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { matchesSearch } from '@/app/settings/lib/search';
import { OTHERS_GROUP } from '@/lib/workspace-picker';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { rowMatchesColumnFilter } from '../users/users-table-filter';
import { downloadTableExport, type UsersExportFormat } from '../users/users-table-export';
import { isOrgAdminRole, orgModulesPath, orgSettingsSectionPath } from '../lib/nav';
import { featureLabel } from '../lib/feature-labels';
import { BulkEditModal } from './bulk-edit-modal';
import '../components/org-settings-components.css';
import '../users/users.css';
import './workspaces.css';

interface OrgWorkspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  organization_id: string;
  created_at: string;
  logo_url?: string | null;
  logo_emoji?: string | null;
  workspace_group?: string | null;
  organization_logo_url?: string | null;
  organization_logo_rectangle_url?: string | null;
  /** The workspace's effective features (its set, within its organization's). */
  features?: string[];
}

type ColumnId = 'workspace' | 'group' | 'owner' | 'members' | 'features' | 'created';
type SortDir = 'asc' | 'desc';

const COLUMNS: { id: ColumnId; label: string; filterable: boolean }[] = [
  { id: 'workspace', label: 'Workspace', filterable: true },
  { id: 'group', label: 'Group', filterable: true },
  { id: 'owner', label: 'Owner', filterable: true },
  { id: 'members', label: 'Members', filterable: false },
  { id: 'features', label: 'Features', filterable: true },
  { id: 'created', label: 'Created', filterable: false },
];

function groupOf(workspace: OrgWorkspace): string {
  return workspace.workspace_group?.trim() || OTHERS_GROUP;
}

function assetUrl(url?: string | null): string {
  if (!url) return '';
  return url.startsWith('/') ? `${getApiUrl()}${url}` : url;
}

/** Feature chips shown in a row; the rest collapses into "+N" (all in the tooltip). */
const FEATURES_SHOWN = 3;

function featuresOf(workspace: OrgWorkspace): string[] {
  return (workspace.features ?? []).map(featureLabel);
}

/** Workspace logo, else the org logo, else the emoji or initial (also when an image fails). */
function WorkspaceLogo({ workspace }: { workspace: OrgWorkspace }) {
  const candidates = [
    assetUrl(workspace.logo_url),
    assetUrl(workspace.organization_logo_url),
    assetUrl(workspace.organization_logo_rectangle_url),
  ].filter(Boolean);
  const [failed, setFailed] = useState(0);
  const src = candidates[failed];
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        className="org-settings-users-avatar-image org-workspaces-logo"
        onError={() => setFailed((count) => count + 1)}
      />
    );
  }
  return (
    <div className="org-settings-users-avatar org-workspaces-logo">
      {workspace.logo_emoji || workspace.name.charAt(0).toUpperCase()}
    </div>
  );
}

function countFacets(values: string[]): FacetBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

/**
 * Organization Settings > Workspaces: every workspace of the organization in a
 * table (search, sort, filters, export), like Organization Settings > Users.
 * Click a row to open the workspace's settings. Admins can select rows to
 * bulk edit their group. A workspace's modules and features are its set,
 * edited on Modules & features (each row links to its column there).
 */
export default function OrganizationWorkspacesPage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const { fetchMembers, membersCache } = useOrganizationStore();

  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [memberCounts, setMemberCounts] = useState<Record<string, number> | null>(null);
  const [viewerRole, setViewerRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<ColumnId>('workspace');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [columnFilters, setColumnFilters] = useState<Partial<Record<ColumnId, ColumnFilterState>>>(
    {}
  );
  const [openFilter, setOpenFilter] = useState<{ id: ColumnId; left: number; top: number } | null>(
    null
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkOpen, setBulkOpen] = useState(false);
  const canManage = isOrgAdminRole(viewerRole);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    (async () => {
      try {
        const [wsRes, orgRes] = await Promise.all([
          authFetch(`/api/organizations/${orgId}/workspaces`),
          authFetch(`/api/organizations/${orgId}`),
        ]);
        if (cancelled) return;
        if (!wsRes.ok) {
          setLoadError(`Failed to load workspaces (HTTP ${wsRes.status}).`);
          return;
        }
        setWorkspaces(await wsRes.json());
        const role = orgRes.ok ? ((await orgRes.json()).current_user_role ?? null) : null;
        setViewerRole(role);
        if (isOrgAdminRole(role)) {
          void fetchMembers(orgId);
          const membersRes = await authFetch(`/api/organizations/${orgId}/member-workspaces`);
          if (membersRes.ok && !cancelled) {
            const data: { memberships: { workspace_id: string }[] } = await membersRes.json();
            const counts: Record<string, number> = {};
            for (const row of data.memberships) {
              counts[row.workspace_id] = (counts[row.workspace_id] || 0) + 1;
            }
            setMemberCounts(counts);
          }
        }
      } catch {
        if (!cancelled) setLoadError('Failed to load workspaces. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId, fetchMembers]);

  const ownerNames = useMemo(() => {
    const names: Record<string, string> = {};
    for (const member of membersCache[orgId] || []) {
      names[member.userId] = member.name || member.email || member.userId;
    }
    return names;
  }, [membersCache, orgId]);

  const ownerName = useCallback(
    (workspace: OrgWorkspace) => ownerNames[workspace.owner_id] || '—',
    [ownerNames]
  );

  const cellValues = useCallback(
    (workspace: OrgWorkspace, columnId: ColumnId): string[] => {
      if (columnId === 'workspace') return [workspace.name, workspace.slug];
      if (columnId === 'group') return [groupOf(workspace)];
      if (columnId === 'features') {
        const features = featuresOf(workspace);
        return features.length ? features : ['None'];
      }
      if (columnId === 'owner') return [ownerName(workspace)];
      if (columnId === 'members') {
        return [memberCounts ? String(memberCounts[workspace.id] || 0) : '—'];
      }
      return [new Date(workspace.created_at).toLocaleDateString()];
    },
    [ownerName, memberCounts]
  );

  const visibleWorkspaces = useMemo(() => {
    const rows = workspaces.filter(
      (workspace) =>
        matchesSearch(
          COLUMNS.flatMap((column) => cellValues(workspace, column.id)),
          search
        ) &&
        COLUMNS.every((column) =>
          rowMatchesColumnFilter(cellValues(workspace, column.id), columnFilters[column.id])
        )
    );
    rows.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'workspace') cmp = a.name.localeCompare(b.name);
      else if (sortKey === 'group') {
        // Others last, whichever the direction of the other groups.
        const ga = groupOf(a);
        const gb = groupOf(b);
        if (ga === OTHERS_GROUP || gb === OTHERS_GROUP) {
          if (ga !== gb) return ga === OTHERS_GROUP ? 1 : -1;
        }
        cmp = ga.localeCompare(gb) || a.name.localeCompare(b.name);
      }
      else if (sortKey === 'features')
        cmp = featuresOf(a).length - featuresOf(b).length || a.name.localeCompare(b.name);
      else if (sortKey === 'owner') cmp = ownerName(a).localeCompare(ownerName(b));
      else if (sortKey === 'members')
        cmp = (memberCounts?.[a.id] || 0) - (memberCounts?.[b.id] || 0);
      else cmp = a.created_at.localeCompare(b.created_at);
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [workspaces, search, columnFilters, cellValues, sortKey, sortDir, ownerName, memberCounts]);

  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      // Every value counts (a workspace has several features).
      const values = workspaces.flatMap((workspace) => cellValues(workspace, columnId as ColumnId));
      return countFacets(values).filter((bucket) => bucket.value.toLowerCase().includes(needle));
    },
    [workspaces, cellValues]
  );

  const toggleSort = (columnId: ColumnId) => {
    if (sortKey === columnId) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(columnId);
    setSortDir(columnId === 'members' || columnId === 'created' ? 'desc' : 'asc');
  };

  const clearFilter = (columnId: ColumnId) =>
    setColumnFilters((current) => {
      const next = { ...current };
      delete next[columnId];
      return next;
    });

  const hasActiveFilters = COLUMNS.some((column) => !isBlank(columnFilters[column.id]));

  const exportVisible = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(
      ['Name', 'Slug', 'Group', 'Owner', 'Members', 'Features', 'Created'],
      visibleWorkspaces.map((workspace) => [
        workspace.name,
        workspace.slug,
        groupOf(workspace),
        ownerName(workspace),
        cellValues(workspace, 'members')[0],
        featuresOf(workspace).join(', '),
        cellValues(workspace, 'created')[0],
      ]),
      format,
      `workspaces_${date}`,
      'Workspaces'
    );
  };

  const createHref = `${orgSettingsSectionPath(orgId, 'workspaces')}/new`;

  // Selection is of visible rows: filtering hides a row, so it leaves the selection.
  const visibleIds = useMemo(() => visibleWorkspaces.map((w) => w.id), [visibleWorkspaces]);
  const selectedVisible = visibleIds.filter((id) => selected.has(id));
  const allSelected = visibleIds.length > 0 && selectedVisible.length === visibleIds.length;
  const someSelected = selectedVisible.length > 0 && !allSelected;

  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(visibleIds));

  const toggleOne = (workspaceId: string, checked: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(workspaceId);
      else next.delete(workspaceId);
      return next;
    });

  const mergeWorkspaces = (updated: OrgWorkspace[]) => {
    const byId = new Map(updated.map((workspace) => [workspace.id, workspace]));
    setWorkspaces((current) => current.map((workspace) => byId.get(workspace.id) ?? workspace));
  };

  const existingGroups = useMemo(
    () =>
      [...new Set(workspaces.map((w) => w.workspace_group?.trim()).filter(Boolean) as string[])].sort(
        (a, b) => a.localeCompare(b)
      ),
    [workspaces]
  );

  const applyBulkEdit = async (_property: 'workspace_group', value: string) => {
    const res = await authFetch(`/api/organizations/${orgId}/workspaces/bulk-update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_ids: selectedVisible, workspace_group: value }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(
        typeof data?.detail === 'string' ? data.detail : `Failed to update (HTTP ${res.status}).`
      );
    }
    const data: { workspaces: OrgWorkspace[] } = await res.json();
    mergeWorkspaces(data.workspaces);
    setSelected(new Set());
    setBulkOpen(false);
  };

  return (
    <div className="org-settings-users-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title="Workspaces"
          badge={`${workspaces.length} ${workspaces.length === 1 ? 'workspace' : 'workspaces'}`}
          subtitle="Workspaces of this organization. Click a row to open its settings."
          actions={
            <>
              {/* Bulk edit: only shown once rows are selected with the checkboxes. */}
              {canManage && selectedVisible.length > 0 && (
                <button
                  type="button"
                  className="org-settings-users-secondary-button"
                  onClick={() => setBulkOpen(true)}
                >
                  <Pencil size={16} />
                  Edit ({selectedVisible.length})
                </button>
              )}
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    type="button"
                    className="org-settings-users-secondary-button"
                    disabled={visibleWorkspaces.length === 0}
                  >
                    <Download size={16} />
                    Export
                    <ChevronDown size={14} />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    align="end"
                    sideOffset={4}
                    className="org-settings-users-export-menu"
                  >
                    <DropdownMenu.Item
                      className="org-settings-users-export-item"
                      onSelect={() => exportVisible('csv')}
                    >
                      CSV
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="org-settings-users-export-item"
                      onSelect={() => exportVisible('xlsx')}
                    >
                      Excel (.xlsx)
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
              <button
                type="button"
                className="org-settings-primary-button"
                onClick={() => router.push(createHref)}
                disabled={!canManage}
                title={
                  canManage ? undefined : 'Only organization owners and admins can create workspaces'
                }
              >
                <Plus size={16} />
                Create workspace
              </button>
            </>
          }
        />

        {loadError && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError}</span>
          </div>
        )}

        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search name, slug, group, owner..."
          label="Search workspaces"
        />

        {(hasActiveFilters || search.trim()) && (
          <p className="org-settings-users-filter-meta">
            {visibleWorkspaces.length} of {workspaces.length}{' '}
            {workspaces.length === 1 ? 'workspace' : 'workspaces'}
            <button
              type="button"
              className="org-settings-users-filter-clear"
              onClick={() => {
                setSearch('');
                setColumnFilters({});
              }}
            >
              Clear search and filters
            </button>
          </p>
        )}

        <div className="org-settings-users-table-wrap">
          {loading ? (
            <div className="org-settings-loading">Loading workspaces...</div>
          ) : workspaces.length === 0 ? (
            <div className="org-settings-empty">
              <div className="org-settings-empty-icon">
                <FolderKanban size={24} />
              </div>
              <p className="org-settings-empty-title">No workspaces yet</p>
              <p className="org-settings-empty-body">
                Use Create workspace at the top right to get started.
              </p>
            </div>
          ) : (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {canManage && (
                    <th className="org-workspaces-select">
                      <Checkbox
                        checked={allSelected}
                        ref={(element) => {
                          if (element) element.indeterminate = someSelected;
                        }}
                        onCheckedChange={toggleAll}
                        disabled={visibleIds.length === 0}
                        aria-label={allSelected ? 'Deselect all' : 'Select all'}
                        title={allSelected ? 'Deselect all' : 'Select all'}
                      />
                    </th>
                  )}
                  {COLUMNS.map((column) => {
                    const sorted = sortKey === column.id;
                    const active = !isBlank(columnFilters[column.id]);
                    return (
                      <th key={column.id}>
                        <div className="org-settings-users-th">
                          <button
                            type="button"
                            className="org-settings-users-sort"
                            onClick={() => toggleSort(column.id)}
                            title="Sort"
                          >
                            <span>{column.label}</span>
                            {sorted && sortDir === 'asc' && <ChevronUp size={12} />}
                            {sorted && sortDir === 'desc' && <ChevronDown size={12} />}
                          </button>
                          {column.filterable && (
                            <button
                              type="button"
                              className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                              data-filter-trigger=""
                              title="Filter"
                              onClick={(event) => {
                                if (openFilter?.id === column.id) {
                                  setOpenFilter(null);
                                  return;
                                }
                                const rect = event.currentTarget.getBoundingClientRect();
                                setOpenFilter({
                                  id: column.id,
                                  left: rect.left,
                                  top: rect.bottom + 4,
                                });
                              }}
                            >
                              <Filter size={11} />
                            </button>
                          )}
                        </div>
                        {openFilter?.id === column.id && (
                          <ColumnFilterPopover
                            columnId={column.id}
                            label={column.label}
                            datatype="string"
                            facetable
                            anchor={{ left: openFilter.left, top: openFilter.top }}
                            state={columnFilters[column.id]}
                            onChange={(next) =>
                              setColumnFilters((current) => ({ ...current, [column.id]: next }))
                            }
                            onClear={() => clearFilter(column.id)}
                            loadFacets={loadFacets}
                            onClose={() => setOpenFilter(null)}
                          />
                        )}
                      </th>
                    );
                  })}
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {visibleWorkspaces.length === 0 && (
                  <tr>
                    <td
                      colSpan={COLUMNS.length + (canManage ? 2 : 1)}
                      className="org-settings-users-no-match"
                    >
                      No workspaces match the current search and filters
                    </td>
                  </tr>
                )}
                {visibleWorkspaces.map((workspace) => {
                  const features = featuresOf(workspace);
                  return (
                    <tr
                      key={workspace.id}
                      className={`org-settings-users-row-link${
                        selected.has(workspace.id) ? ' org-workspaces-row-selected' : ''
                      }`}
                      onClick={(event) => {
                        if ((event.target as HTMLElement).closest('a, button, input, label')) return;
                        router.push(`/workspace/${workspace.id}/settings`);
                      }}
                    >
                      {canManage && (
                        <td className="org-workspaces-select">
                          <Checkbox
                            checked={selected.has(workspace.id)}
                            onCheckedChange={(checked) => toggleOne(workspace.id, checked)}
                            aria-label={`Select ${workspace.name}`}
                          />
                        </td>
                      )}
                      <td>
                        <div className="org-settings-users-row-start">
                          <WorkspaceLogo workspace={workspace} />
                          <div className="org-settings-users-identity">
                            <p className="org-settings-users-name">{workspace.name}</p>
                            <p className="org-settings-users-email">/{workspace.slug}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span
                          className={
                            groupOf(workspace) === OTHERS_GROUP
                              ? 'org-settings-users-email'
                              : undefined
                          }
                        >
                          {groupOf(workspace)}
                        </span>
                      </td>
                      <td>{ownerName(workspace)}</td>
                      <td>{cellValues(workspace, 'members')[0]}</td>
                      <td>
                        <span
                          className="org-workspaces-features"
                          title={features.join(', ') || 'No features'}
                        >
                          {features.length ? (
                            <>
                              {features.slice(0, FEATURES_SHOWN).map((feature) => (
                                <span key={feature} className="org-workspaces-feature">
                                  {feature}
                                </span>
                              ))}
                              {features.length > FEATURES_SHOWN && (
                                <span className="org-workspaces-feature org-workspaces-feature-more">
                                  +{features.length - FEATURES_SHOWN}
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="org-settings-users-email">None</span>
                          )}
                        </span>
                      </td>
                      <td>
                        <span className="org-settings-users-email">
                          {cellValues(workspace, 'created')[0]}
                        </span>
                      </td>
                      <td>
                        <div className="org-workspaces-actions">
                          <Link
                            href={orgModulesPath(orgId, workspace.id)}
                            className="org-settings-users-secondary-button org-workspaces-open"
                            title="The modules and features this workspace may use"
                          >
                            <Blocks size={14} />
                            Modules & features
                          </Link>
                          <Link
                            href={`/workspace/${workspace.id}/home`}
                            className="org-settings-users-secondary-button org-workspaces-open"
                          >
                            <ExternalLink size={14} />
                            Open
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <p className="org-settings-footnote">
          Members counts workspace members; org owners and admins reach every workspace anyway.
          Workspaces inherit the organization branding unless they set their own logo. Features
          lists what the workspace has; Modules & features sets what each workspace may use.
        </p>

        <BulkEditModal
          open={bulkOpen}
          count={selectedVisible.length}
          groups={existingGroups}
          onClose={() => setBulkOpen(false)}
          onApply={applyBulkEdit}
        />
      </div>
    </div>
  );
}
