'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { Button } from '@/components/ui/button';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  countLabel,
} from '@/components/settings/settings-ui';
import { TablePager, usePagedRows } from '@/components/settings/users-table/table-pager';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';
import { matchesSearch } from '@/app/settings/lib/search';
import { countFacets } from '@/app/settings/lib/page-helpers';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { createFeatureAccessApi, type FeatureAccessApi } from './feature-access-api';
import {
  FEATURE_COLUMNS,
  FEATURE_EXPORT_HEADERS,
  changesFrom,
  choicesOf,
  draftOf,
  featureCellValues,
  featureExportRow,
  featureSearchTexts,
  otherPolicies,
  rowNotes,
  sortFeatures,
  type FeatureAccessState,
  type FeatureChoice,
  type FeatureColumnId,
  type FeatureDraft,
  type FeatureRow,
  type SortDir,
} from './feature-access-model';

const DEFAULT_API = createFeatureAccessApi();

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/** The Files feature (Workspace Files) is Settings › Files', with the other files a workspace gives. */
const FILES_FEATURE = 'files';

/**
 * Settings › Features, laid out as Settings › Users (a header with its count and actions, a search,
 * a table whose columns sort and filter, pages, an export): one row per enabled feature but Files
 * (Settings › Files), whether the workspace offers it, Everyone or Nobody. A feature is part of the
 * workspace's offer, its access policy "<W> access" (the API writes it as the caller), edited with
 * its agents, apps, workflows and pipelines on that policy's page; a row is editable when IAM lets
 * the caller give the feature here. Other policies naming a feature are listed with it (a Deny
 * wins), and a statement written on the policy's page is shown read-only. Several rows are saved in
 * one step.
 */
export function FeatureAccess({ workspaceId, api = DEFAULT_API }: { workspaceId: string; api?: FeatureAccessApi }) {
  const [state, setState] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [drafts, setDrafts] = useState<Record<string, FeatureDraft>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<Partial<Record<FeatureColumnId, ColumnFilterState>>>({});
  const [sortKey, setSortKey] = useState<FeatureColumnId>('feature');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [openFilter, setOpenFilter] = useState<{ id: FeatureColumnId; left: number; top: number } | null>(null);

  const load = useCallback(async () => {
    try {
      setState(await api.read(workspaceId));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read who uses the features.'));
    }
  }, [api, workspaceId]);

  useEffect(() => {
    setState(null);
    setDrafts({});
    setRowErrors({});
    void load();
  }, [load]);

  const rows = useMemo(() => (state?.features ?? []).filter((row) => row.key !== FILES_FEATURE), [state]);
  const shown = useMemo(
    () =>
      sortFeatures(
        rows.filter(
          (row) =>
            matchesSearch(featureSearchTexts(row), searchQuery) &&
            FEATURE_COLUMNS.every((column) => rowMatchesColumnFilter(featureCellValues(row, column.id), filters[column.id]))
        ),
        sortKey,
        sortDir
      ),
    [rows, searchQuery, filters, sortKey, sortDir]
  );
  const paged = usePagedRows(shown, JSON.stringify([searchQuery, filters, sortKey, sortDir]));
  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      return countFacets(rows.flatMap((row) => featureCellValues(row, columnId as FeatureColumnId))).filter((bucket) =>
        bucket.value.toLowerCase().includes(needle)
      );
    },
    [rows]
  );

  const draftFor = (row: FeatureRow) => drafts[row.key] ?? draftOf(row);
  const changes = changesFrom(rows, drafts);

  const choose = (row: FeatureRow, choice: FeatureChoice) =>
    setDrafts((current): Record<string, FeatureDraft> => ({ ...current, [row.key]: { choice } }));

  const save = async () => {
    setSaving(true);
    try {
      const next = await api.save(workspaceId, changes);
      const refused = next.errors ?? {};
      setState(next);
      setRowErrors(refused);
      setDrafts((current) => Object.fromEntries(Object.entries(current).filter(([key]) => refused[key])));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const discard = () => {
    setDrafts({});
    setRowErrors({});
  };

  const toggleSort = (column: FeatureColumnId) => {
    if (sortKey === column) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(column);
    setSortDir('asc');
  };
  const filtered = searchQuery.trim() !== '' || FEATURE_COLUMNS.some((column) => !isBlank(filters[column.id]));
  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(FEATURE_EXPORT_HEADERS, shown.map(featureExportRow), format, `features_${date}`, 'Features');
  };

  const access = state?.access_policy ?? null;
  const offerHref = access ? ownerHref(access.owner_scope, access.id) : null;
  const offeredCount = rows.filter((row) => row.choice === 'everyone').length;
  const unsaved =
    changes.length === 0 ? 'No unsaved change' : `${changes.length} unsaved change${changes.length === 1 ? '' : 's'}`;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Features"
        badge={state ? `${offeredCount} offered · ${rows.length - offeredCount} not offered` : undefined}
        description={
          <>
            Whether this workspace offers each feature: Everyone in it, or Nobody. Each person&apos;s level decides
            what they may do with it, admins included. Part of what the workspace offers
            {offerHref && access ? (
              <>
                {' '}
                (<Link href={offerHref}>{access.name}</Link>)
              </>
            ) : null}
            ; files are in <Link href={`/workspace/${workspaceId}/settings/files`}>Files</Link>.
          </>
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />
            <Button
              variant="secondary"
              data-action="discard"
              disabled={saving || (changes.length === 0 && Object.keys(rowErrors).length === 0)}
              onClick={discard}
            >
              Discard
            </Button>
            <Button
              disabled={saving || changes.length === 0}
              onClick={() => void save()}
              data-action="save"
            >
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </>
        }
      />

      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </SettingsNotice>
      )}

      {!state ? (
        !error && <SettingsLoading label="Loading features…" />
      ) : rows.length === 0 ? (
        <SettingsEmpty title="No features." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={searchQuery}
            onSearchChange={setSearchQuery}
            searchPlaceholder="Search feature, everyone, nobody, policy, not offered…"
            meta={
              <>
                {`${countLabel(shown.length, rows.length, 'feature')} · ${unsaved}`}
                {filtered && (
                  <button
                    type="button"
                    className="org-settings-users-filter-clear ml-3"
                    data-action="clear-filters"
                    onClick={() => {
                      setSearchQuery('');
                      setFilters({});
                    }}
                  >
                    Clear search and filters
                  </button>
                )}
              </>
            }
          />
          <p className="text-xs text-muted-foreground">
            Other policies may grant or deny a feature too, and a Deny always wins.
          </p>
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {FEATURE_COLUMNS.map((column) => {
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
                            data-filter-trigger={column.id}
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
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={FEATURE_COLUMNS.length} className="org-settings-users-no-match">
                      No features match the current search and filters
                    </td>
                  </tr>
                )}
                {paged.pageRows.map((row) => {
                  const draft = draftFor(row);
                  return (
                    <tr key={row.key} data-feature={row.key} className="align-top">
                      <td>
                        <p className="font-medium text-foreground">{row.label}</p>
                        <p className="text-xs text-muted-foreground">{row.key}</p>
                      </td>
                      <td data-field="offered">
                        <div
                          className="workspace-features-choices"
                          role="radiogroup"
                          aria-label={`Who ${row.label} is offered to`}
                        >
                          {choicesOf(row).map((choice) => (
                            <button
                              key={choice.value}
                              type="button"
                              role="radio"
                              aria-checked={draft.choice === choice.value}
                              data-choice={choice.value}
                              title={choice.hint}
                              disabled={!choice.enabled || saving}
                              className="workspace-features-choice"
                              onClick={() => choose(row, choice.value)}
                            >
                              {choice.label}
                            </button>
                          ))}
                        </div>
                        {rowNotes(row, state).map((note) => (
                          <p key={note.text} className="workspace-features-note" data-tone={note.tone}>
                            {note.text}
                            {note.href && note.link ? (
                              <>
                                {' '}
                                <Link href={note.href}>{note.link}</Link>
                              </>
                            ) : null}
                          </p>
                        ))}
                        {rowErrors[row.key] && (
                          <p className="workspace-features-error" role="alert">
                            {rowErrors[row.key]}
                          </p>
                        )}
                      </td>
                      <td data-field="policies">
                        {row.also.length === 0 ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          <ul className="workspace-features-also">
                            {otherPolicies(row).map(({ policy, text, href }) => (
                              <li key={policy.id} data-effect={policy.effect}>
                                {href ? <Link href={href}>{text}</Link> : text}
                              </li>
                            ))}
                          </ul>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <TablePager total={shown.length} paged={paged} />
    </div>
  );
}
