'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  AlertCircle,
  Building2,
  ChevronDown,
  ChevronUp,
  Download,
  Filter,
  Pencil,
  Plus,
  RefreshCw,
  Settings,
  Trash2,
} from 'lucide-react';
import { getApiUrl } from '@/lib/config';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { SearchBox } from '@/components/settings/search-box';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';
import {
  downloadTableExport,
  type UsersExportFormat,
} from '@/components/settings/users-table/users-table-export';
import { countFacets } from '../lib/page-helpers';
import { deleteOrganization, listOrganizations, renameOrganization, type Fetcher } from './organizations-api';
import {
  createdDay,
  deleteConfirmed,
  matchesOrganization,
  NEW_ORGANIZATION_PATH,
  ORGANIZATION_COLUMNS,
  ORGANIZATION_EXPORT_HEADERS,
  organizationCellValues,
  organizationCount,
  organizationExportRow,
  organizationLocation,
  sortOrganizationsBy,
  websiteLabel,
  type OrganizationColumnId,
  type PlatformOrganization,
} from './organizations-model';
import '../users/users.css';
import './organizations.css';

type Panel = { mode: 'none' } | { mode: 'rename'; name: string } | { mode: 'delete'; typed: string };

/** The organization's own settings, which a row opens. */
export function organizationSettingsHref(id: string): string {
  return `/organizations/${encodeURIComponent(id)}/settings`;
}

function logoUrl(url: string | null | undefined): string {
  if (!url) return '';
  return url.startsWith('/') ? `${getApiUrl()}${url}` : url;
}

function OrganizationRow({
  organization,
  fetcher,
  navigate,
  onChanged,
}: {
  organization: PlatformOrganization & { logo_url?: string | null };
  fetcher?: Fetcher;
  navigate: (href: string) => void;
  onChanged: () => void;
}) {
  const [panel, setPanel] = useState<Panel>({ mode: 'none' });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const href = organizationSettingsHref(organization.id);

  const rename = async () => {
    if (panel.mode !== 'rename' || !panel.name.trim()) return;
    setBusy(true);
    const answer = await renameOrganization(organization.id, panel.name.trim(), fetcher);
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setError(null);
    setPanel({ mode: 'none' });
    onChanged();
  };

  const remove = async () => {
    if (panel.mode !== 'delete' || !deleteConfirmed(organization, panel.typed)) return;
    setBusy(true);
    const answer = await deleteOrganization(organization.id, fetcher);
    setBusy(false);
    if (!answer.ok) {
      setError(answer.error);
      return;
    }
    setError(null);
    setPanel({ mode: 'none' });
    onChanged();
  };

  const logo = logoUrl(organization.logo_url);
  const location = organizationLocation(organization);
  const website = websiteLabel(organization.website);

  return (
    <>
      <tr
        data-org={organization.id}
        className="org-settings-users-row-link"
        title="Open its settings"
        onClick={(event) => {
          // The row's own buttons, links and forms keep their action.
          if ((event.target as HTMLElement).closest('button, a, input, form')) return;
          navigate(href);
        }}
      >
        <td>
          <div className="org-settings-users-row-start">
            {logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={logo} alt="" className="org-settings-users-avatar-image platform-orgs-logo" />
            ) : (
              <div className="org-settings-users-avatar platform-orgs-logo">
                {(organization.name || '?').charAt(0).toUpperCase()}
              </div>
            )}
            <div className="org-settings-users-identity">
              <p className="org-settings-users-name">{organization.name}</p>
              <p className="org-settings-users-email">{organization.slug}</p>
            </div>
          </div>
        </td>
        <td className="platform-users-mono">{organization.id}</td>
        <td data-field="legal_name">
          {organization.legal_name || <span className="platform-users-muted">—</span>}
        </td>
        <td data-field="location">{location || <span className="platform-users-muted">—</span>}</td>
        <td data-field="website">
          {website ? (
            <a
              className="platform-orgs-website"
              href={organization.website ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
            >
              {website}
            </a>
          ) : (
            <span className="platform-users-muted">—</span>
          )}
        </td>
        <td>{createdDay(organization)}</td>
        <td className="platform-users-actions-cell">
          <span className="org-settings-users-row-actions platform-users-actions">
            <Link
              href={href}
              className="org-settings-users-edit"
              data-action="settings"
              title="Settings"
              aria-label={`Open the settings of ${organization.name}`}
            >
              <Settings size={16} />
            </Link>
            <button
              type="button"
              className="org-settings-users-edit"
              data-action="rename"
              title="Rename"
              aria-label={`Rename ${organization.name}`}
              onClick={() => {
                setError(null);
                setPanel({ mode: 'rename', name: organization.name });
              }}
            >
              <Pencil size={16} />
            </button>
            <button
              type="button"
              className="org-settings-users-remove"
              data-action="delete"
              title="Delete"
              aria-label={`Delete ${organization.name}`}
              onClick={() => {
                setError(null);
                setPanel({ mode: 'delete', typed: '' });
              }}
            >
              <Trash2 size={16} />
            </button>
          </span>
        </td>
      </tr>
      {(panel.mode !== 'none' || error) && (
        <tr className="platform-users-panel-row" data-panel={organization.id}>
          <td colSpan={ORGANIZATION_COLUMNS.length + 1}>
            {panel.mode === 'rename' && (
              <form
                className="platform-users-inline"
                onSubmit={(event) => {
                  event.preventDefault();
                  void rename();
                }}
              >
                <input
                  className="platform-users-input"
                  aria-label={`New name of ${organization.name}`}
                  data-field="rename"
                  value={panel.name}
                  onChange={(event) => setPanel({ mode: 'rename', name: event.target.value })}
                />
                <button
                  type="submit"
                  className="platform-users-button"
                  data-action="save"
                  disabled={busy || !panel.name.trim()}
                >
                  Save
                </button>
                <button type="button" className="platform-users-button" onClick={() => setPanel({ mode: 'none' })}>
                  Cancel
                </button>
              </form>
            )}
            {panel.mode === 'delete' && (
              <form
                className="platform-users-inline"
                onSubmit={(event) => {
                  event.preventDefault();
                  void remove();
                }}
              >
                <span className="platform-users-confirm-text">
                  Type <strong>{organization.name}</strong> to delete it. An organization is deleted once it has
                  no workspace left.
                </span>
                <input
                  className="platform-users-input"
                  aria-label={`Type ${organization.name} to confirm`}
                  data-field="confirm"
                  value={panel.typed}
                  onChange={(event) => setPanel({ mode: 'delete', typed: event.target.value })}
                />
                <button
                  type="submit"
                  className="platform-users-button platform-users-button-danger"
                  data-action="confirm-delete"
                  disabled={busy || !deleteConfirmed(organization, panel.typed)}
                >
                  Delete organization
                </button>
                <button type="button" className="platform-users-button" onClick={() => setPanel({ mode: 'none' })}>
                  Cancel
                </button>
              </form>
            )}
            {error && (
              <p className="platform-users-error" role="alert">
                {error}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

/** Every organization the caller may list, as a table like Users: open, rename, delete. */
export function PlatformOrganizations({
  fetcher,
  navigate = () => undefined,
}: {
  fetcher?: Fetcher;
  navigate?: (href: string) => void;
}) {
  const [organizations, setOrganizations] = useState<PlatformOrganization[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<OrganizationColumnId>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [filters, setFilters] = useState<Partial<Record<OrganizationColumnId, ColumnFilterState>>>({});
  const [openFilter, setOpenFilter] = useState<{ id: OrganizationColumnId; left: number; top: number } | null>(
    null
  );

  const reload = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    let live = true;
    void listOrganizations(fetcher).then((answer) => {
      if (!live) return;
      if (answer.ok) {
        setOrganizations(answer.data ?? []);
        setLoadError(null);
      } else {
        setLoadError(answer.error);
      }
    });
    return () => {
      live = false;
    };
  }, [fetcher, reloads]);

  const all = useMemo(() => organizations ?? [], [organizations]);
  const visible = useMemo(
    () =>
      sortOrganizationsBy(
        all.filter(
          (org) =>
            matchesOrganization(org, search) &&
            ORGANIZATION_COLUMNS.every((column) =>
              rowMatchesColumnFilter(organizationCellValues(org, column.id), filters[column.id])
            )
        ),
        sortKey,
        sortDir
      ),
    [all, search, filters, sortKey, sortDir]
  );

  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      return countFacets(
        all.flatMap((org) => organizationCellValues(org, columnId as OrganizationColumnId))
      ).filter((bucket) => bucket.value.toLowerCase().includes(needle));
    },
    [all]
  );

  const exportVisible = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(
      ORGANIZATION_EXPORT_HEADERS,
      visible.map(organizationExportRow),
      format,
      `organizations_${date}`,
      'Organizations'
    );
  };

  const filtered =
    search.trim() !== '' || ORGANIZATION_COLUMNS.some((column) => !isBlank(filters[column.id]));

  const toggleSort = (column: OrganizationColumnId) => {
    if (sortKey === column) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(column);
    setSortDir('asc');
  };

  return (
    <div className="org-settings-users-page platform-users-page platform-orgs-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title="Organizations"
          badge={organizations ? organizationCount(organizations.length) : undefined}
          subtitle="Every organization of the platform: open its settings, rename it, delete it once it has no workspace left"
          actions={
            <>
              <button
                type="button"
                className="org-settings-users-secondary-button"
                data-action="refresh"
                onClick={() => reload()}
                title="Refresh"
                aria-label="Refresh"
              >
                <RefreshCw size={16} />
              </button>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    type="button"
                    className="org-settings-users-secondary-button"
                    data-action="export"
                    disabled={visible.length === 0}
                  >
                    <Download size={16} />
                    Export
                    <ChevronDown size={14} />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content align="end" sideOffset={4} className="org-settings-users-export-menu">
                    <DropdownMenu.Item className="org-settings-users-export-item" onSelect={() => exportVisible('csv')}>
                      CSV
                    </DropdownMenu.Item>
                    <DropdownMenu.Item className="org-settings-users-export-item" onSelect={() => exportVisible('xlsx')}>
                      Excel (.xlsx)
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
              <Link
                href={NEW_ORGANIZATION_PATH}
                className="org-settings-primary-button"
                data-action="new"
                title="New organization"
              >
                <Plus size={16} />
                New
              </Link>
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
          placeholder="Search name, slug, ID, legal name, location, website…"
          label="Search organizations"
        />

        {filtered && (
          <p className="org-settings-users-filter-meta">
            {visible.length} of {organizationCount(all.length)}
            <button
              type="button"
              className="org-settings-users-filter-clear"
              onClick={() => {
                setSearch('');
                setFilters({});
              }}
            >
              Clear search and filters
            </button>
          </p>
        )}

        <div className="org-settings-users-table-wrap">
          {organizations === null && !loadError ? (
            <div className="org-settings-loading">Loading organizations…</div>
          ) : organizations !== null && organizations.length === 0 ? (
            <div className="org-settings-empty">
              <div className="org-settings-empty-icon">
                <Building2 size={24} />
              </div>
              <p className="org-settings-empty-title">No organizations yet</p>
            </div>
          ) : organizations !== null ? (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {ORGANIZATION_COLUMNS.map((column) => {
                    const sorted = sortKey === column.id;
                    const active = !isBlank(filters[column.id]);
                    return (
                      <th key={column.id}>
                        <div className="org-settings-users-th">
                          <button
                            type="button"
                            className="org-settings-users-sort"
                            data-sort={column.id}
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
                            data-filter={column.id}
                            title="Filter"
                            onClick={(event) => {
                              if (openFilter?.id === column.id) {
                                setOpenFilter(null);
                                return;
                              }
                              const rect = event.currentTarget.getBoundingClientRect();
                              setOpenFilter({ id: column.id, left: rect.left, top: rect.bottom + 4 });
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
                            state={filters[column.id]}
                            onChange={(next) => setFilters((current) => ({ ...current, [column.id]: next }))}
                            onClear={() =>
                              setFilters((current) => {
                                const next = { ...current };
                                delete next[column.id];
                                return next;
                              })
                            }
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
                {visible.length === 0 && (
                  <tr>
                    <td colSpan={ORGANIZATION_COLUMNS.length + 1} className="org-settings-users-no-match">
                      No organizations match the current search and filters
                    </td>
                  </tr>
                )}
                {visible.map((organization) => (
                  <OrganizationRow
                    key={organization.id}
                    organization={organization}
                    fetcher={fetcher}
                    navigate={navigate}
                    onChanged={reload}
                  />
                ))}
              </tbody>
            </table>
          ) : null}
        </div>

        <p className="org-settings-footnote">
          A row opens the organization&apos;s own settings: its general information, branding, members and
          workspaces. An organization is deleted only once it has no workspace left.
        </p>
      </div>
    </div>
  );
}

export default function PlatformOrganizationsPage() {
  const router = useRouter();
  const navigate = useCallback((href: string) => router.push(href), [router]);
  return <PlatformOrganizations navigate={navigate} />;
}
