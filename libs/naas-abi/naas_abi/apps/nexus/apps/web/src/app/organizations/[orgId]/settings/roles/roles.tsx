'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { AlertCircle, ChevronDown, ChevronUp, Filter, Save } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { useOrganizationStore } from '@/stores/organization';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { SearchBox } from '@/components/settings/search-box';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { Checkbox } from '@/components/ui/checkbox';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { matchesSearch } from '@/app/settings/lib/search';
import { rowMatchesColumnFilter } from '../users/users-table-filter';
import { FEATURE_LABELS, featureLabel, sortFeaturesByName } from '../lib/feature-labels';
import '../components/org-settings-components.css';
import '../users/users.css';
import './roles.css';

type RoleName = 'owner' | 'admin' | 'member' | 'viewer';

type RoleFeaturesResponse = {
  enabled_features: string[];
  role_baseline: Record<string, string[]>;
  known_features: string[];
  roles: RoleName[];
  persistence?: 'database' | 'deployment' | string;
  note?: string;
};

const ROLE_LABELS: Record<RoleName, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
};

/** Matrix column order (least to most privileged). */
const ROLE_MATRIX_ORDER: RoleName[] = ['viewer', 'member', 'admin', 'owner'];

/** Owner baseline comes from deployment; it is shown but not editable here. */
const ROLE_MATRIX_READ_ONLY: RoleName = 'owner';

function orderRolesForMatrix(roles: RoleName[]): RoleName[] {
  const known = new Set(roles);
  return ROLE_MATRIX_ORDER.filter((role) => known.has(role));
}

function emptyBaseline(roles: RoleName[]): Record<RoleName, string[]> {
  return {
    owner: [],
    admin: [],
    member: [],
    viewer: [],
    ...Object.fromEntries(roles.map((role) => [role, []])),
  } as Record<RoleName, string[]>;
}

type ColumnId = 'feature' | RoleName;
type SortDir = 'asc' | 'desc';

const GRANT_LABEL = { granted: 'Granted', denied: 'Not granted' } as const;

function countFacets(values: string[]): FacetBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

export default function OrgRolesPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const authUser = useAuthStore((s) => s.user);
  const { fetchMembers, membersCache } = useOrganizationStore();
  const members = membersCache[orgId] || [];
  const myMembership = members.find((m) => m.userId === authUser?.id);
  const canManage =
    myMembership?.role === 'owner' || myMembership?.role === 'admin';

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortKey, setSortKey] = useState<ColumnId>('feature');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [columnFilters, setColumnFilters] = useState<
    Partial<Record<ColumnId, ColumnFilterState>>
  >({});
  const [openFilter, setOpenFilter] = useState<{
    id: ColumnId;
    left: number;
    top: number;
  } | null>(null);
  const [persistence, setPersistence] = useState('deployment');
  const [features, setFeatures] = useState<string[]>([]);
  const [roles, setRoles] = useState<RoleName[]>(() =>
    orderRolesForMatrix(['owner', 'admin', 'member', 'viewer'])
  );
  const [baseline, setBaseline] = useState<Record<RoleName, string[]>>(
    emptyBaseline(['owner', 'admin', 'member', 'viewer'])
  );
  const [initialBaseline, setInitialBaseline] = useState<
    Record<RoleName, string[]>
  >(emptyBaseline(['owner', 'admin', 'member', 'viewer']));

  useEffect(() => {
    if (orgId) {
      void fetchMembers(orgId);
    }
  }, [orgId, fetchMembers]);

  useEffect(() => {
    const load = async () => {
      if (!orgId) return;
      setLoading(true);
      setError('');
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(
          `/api/organizations/${orgId}/roles/features`
        );
        if (!response.ok) {
          throw new Error('Failed to load role features');
        }
        const data: RoleFeaturesResponse = await response.json();
        const nextRoles = (data.roles || [
          'owner',
          'admin',
          'member',
          'viewer',
        ]) as RoleName[];
        const nextFeatures =
          data.enabled_features?.length > 0
            ? data.enabled_features
            : data.known_features || [];
        const nextBaseline = emptyBaseline(nextRoles);
        for (const role of nextRoles) {
          nextBaseline[role] = [...(data.role_baseline?.[role] || [])];
        }
        setRoles(orderRolesForMatrix(nextRoles));
        setFeatures(sortFeaturesByName(nextFeatures));
        setBaseline(nextBaseline);
        setInitialBaseline({
          owner: [...nextBaseline.owner],
          admin: [...nextBaseline.admin],
          member: [...nextBaseline.member],
          viewer: [...nextBaseline.viewer],
        });
        setPersistence(data.persistence || 'deployment');
        setNote(data.note || '');
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : 'Failed to load role features'
        );
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [orgId]);

  const dirty = useMemo(() => {
    return roles
      .filter((role) => role !== ROLE_MATRIX_READ_ONLY)
      .some((role) => {
        const a = [...(baseline[role] || [])].sort().join(',');
        const b = [...(initialBaseline[role] || [])].sort().join(',');
        return a !== b;
      });
  }, [baseline, initialBaseline, roles]);

  const toggleFeature = (role: RoleName, feature: string) => {
    if (!canManage || role === ROLE_MATRIX_READ_ONLY) return;
    setBaseline((current) => {
      const existing = new Set(current[role] || []);
      if (existing.has(feature)) {
        existing.delete(feature);
      } else {
        existing.add(feature);
      }
      return {
        ...current,
        [role]: features.filter((key) => existing.has(key)),
      };
    });
  };

  const columns = useMemo(
    (): { id: ColumnId; label: string }[] => [
      { id: 'feature', label: 'Feature' },
      ...roles.map((role) => ({ id: role, label: ROLE_LABELS[role] || role })),
    ],
    [roles]
  );

  const cellValues = useCallback(
    (feature: string, columnId: ColumnId): string[] => {
      if (columnId === 'feature') {
        return [featureLabel(feature), feature];
      }
      const granted = (baseline[columnId] || []).includes(feature);
      return [granted ? GRANT_LABEL.granted : GRANT_LABEL.denied];
    },
    [baseline]
  );

  const loadFacets = useCallback(
    async (columnId: string, search: string): Promise<FacetBucket[]> => {
      const needle = search.trim().toLowerCase();
      const values = features.flatMap((feature) =>
        cellValues(feature, columnId as ColumnId)
      );
      return countFacets(values).filter((bucket) =>
        bucket.value.toLowerCase().includes(needle)
      );
    },
    [features, cellValues]
  );

  const visibleFeatures = useMemo(() => {
    const query = searchQuery.trim();
    const rows = features.filter(
      (feature) =>
        matchesSearch(
          columns.flatMap((column) => cellValues(feature, column.id)),
          query
        ) &&
        columns.every((column) =>
          rowMatchesColumnFilter(
            cellValues(feature, column.id),
            columnFilters[column.id]
          )
        )
    );
    rows.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'feature') {
        cmp = featureLabel(a).localeCompare(featureLabel(b));
      } else {
        const aGranted = (baseline[sortKey] || []).includes(a);
        const bGranted = (baseline[sortKey] || []).includes(b);
        cmp =
          Number(aGranted) - Number(bGranted) ||
          featureLabel(a).localeCompare(featureLabel(b));
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [
    features,
    searchQuery,
    columns,
    cellValues,
    columnFilters,
    sortKey,
    sortDir,
    baseline,
  ]);

  const toggleSort = (columnId: ColumnId) => {
    if (sortKey === columnId) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(columnId);
    setSortDir(columnId === 'feature' ? 'asc' : 'desc');
  };

  const setFilter = (columnId: ColumnId, next: ColumnFilterState) => {
    setColumnFilters((current) => ({ ...current, [columnId]: next }));
  };

  const clearFilter = (columnId: ColumnId) => {
    setColumnFilters((current) => {
      const next = { ...current };
      delete next[columnId];
      return next;
    });
  };

  const handleSave = async () => {
    if (!orgId || !canManage || !dirty) return;
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const { authFetch } = await import('@/stores/auth');
      const response = await authFetch(
        `/api/organizations/${orgId}/roles/features`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role_baseline: Object.fromEntries(
              roles.map((role) => [role, baseline[role] || []])
            ),
          }),
        }
      );
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to save role features');
      }
      const data: RoleFeaturesResponse = await response.json();
      if (data.persistence !== 'database') {
        throw new Error(
          'Save did not persist to the database. Try again or contact support.'
        );
      }
      const nextBaseline = emptyBaseline(roles);
      for (const role of roles) {
        nextBaseline[role] = [...(data.role_baseline?.[role] || [])];
      }
      setBaseline(nextBaseline);
      setInitialBaseline({
        owner: [...nextBaseline.owner],
        admin: [...nextBaseline.admin],
        member: [...nextBaseline.member],
        viewer: [...nextBaseline.viewer],
      });
      setPersistence(data.persistence);
      setNote(data.note || note);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to save role features'
      );
    } finally {
      setSaving(false);
    }
  };

  const hasActiveFilters =
    columns.some((column) => !isBlank(columnFilters[column.id])) ||
    searchQuery.trim().length > 0;

  if (loading) {
    return <div className="org-settings-loading">Loading roles...</div>;
  }

  const footnote =
    note ||
    (persistence === 'database'
      ? 'Role feature access for this organization is saved in the database and applies across API workers and restarts.'
      : 'Role feature access currently uses the deployment baseline from nexus_config.feature_flags. Save writes a durable organization overlay.');

  return (
    <div className="org-settings-roles-page org-settings-users-page">
      <div className="org-settings-users-main">
      <OrgSettingsPageHeader
        title="Roles"
        badge={`${roles.length} ${roles.length === 1 ? 'role' : 'roles'}`}
        subtitle="Define which workspace features each role can access. Owner access is fixed."
        actions={
          canManage ? (
            <button
              type="button"
              className={
                saved
                  ? 'org-settings-primary-button org-settings-primary-button-saved'
                  : 'org-settings-primary-button'
              }
              onClick={() => void handleSave()}
              disabled={!dirty || saving}
            >
              <Save size={16} />
              {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Changes'}
            </button>
          ) : undefined
        }
      />

      {error && (
        <div className="org-settings-users-alert" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <SearchBox
        value={searchQuery}
        onChange={setSearchQuery}
        placeholder="Search features..."
        label="Search features"
      />

      {hasActiveFilters && (
        <p className="org-settings-users-filter-meta">
          {visibleFeatures.length} of {features.length}{' '}
          {features.length === 1 ? 'feature' : 'features'}
          {dirty ? ' · unsaved changes' : ''}
          <button
            type="button"
            className="org-settings-users-filter-clear"
            onClick={() => {
              setSearchQuery('');
              setColumnFilters({});
            }}
          >
            Clear search and filters
          </button>
        </p>
      )}

      <div className="org-settings-users-table-wrap">
        <table className="org-settings-users-table org-settings-roles-table">
          <thead>
            <tr>
              {columns.map((column) => {
                const sorted = sortKey === column.id;
                const active = !isBlank(columnFilters[column.id]);
                const readOnlyHeader =
                  column.id !== 'feature' && column.id === ROLE_MATRIX_READ_ONLY;
                return (
                  <th
                    key={column.id}
                    scope="col"
                    className={
                      column.id === 'feature'
                        ? undefined
                        : readOnlyHeader
                          ? 'org-settings-roles-col-readonly org-settings-roles-role-col'
                          : 'org-settings-roles-role-col'
                    }
                    title={
                      readOnlyHeader ? 'Owner access cannot be changed' : undefined
                    }
                  >
                    <div
                      className={
                        column.id === 'feature'
                          ? 'org-settings-users-th'
                          : 'org-settings-users-th org-settings-roles-role-header'
                      }
                    >
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
                    </div>
                    {openFilter?.id === column.id && (
                      <ColumnFilterPopover
                        columnId={column.id}
                        label={column.label}
                        datatype="string"
                        facetable
                        anchor={{ left: openFilter.left, top: openFilter.top }}
                        state={columnFilters[column.id]}
                        onChange={(next) => setFilter(column.id, next)}
                        onClear={() => clearFilter(column.id)}
                        loadFacets={loadFacets}
                        onClose={() => setOpenFilter(null)}
                      />
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleFeatures.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="org-settings-users-no-match">
                  No features match the current search and filters
                </td>
              </tr>
            )}
            {visibleFeatures.map((feature) => (
              <tr key={feature}>
                <td className="org-settings-roles-feature-cell">
                  {FEATURE_LABELS[feature] || feature}
                </td>
                {roles.map((role) => {
                  const checked = (baseline[role] || []).includes(feature);
                  const readOnly = role === ROLE_MATRIX_READ_ONLY;
                  return (
                    <td
                      key={`${role}-${feature}`}
                      className={
                        readOnly
                          ? 'org-settings-roles-col-readonly org-settings-roles-role-col'
                          : 'org-settings-roles-role-col'
                      }
                    >
                      <label className="org-settings-roles-check">
                        <Checkbox
                          checked={checked}
                          disabled={!canManage || readOnly}
                          onCheckedChange={() => toggleFeature(role, feature)}
                          aria-label={`${ROLE_LABELS[role]} can access ${FEATURE_LABELS[feature] || feature}`}
                        />
                      </label>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="org-settings-footnote">{footnote}</p>
      </div>
    </div>
  );
}
