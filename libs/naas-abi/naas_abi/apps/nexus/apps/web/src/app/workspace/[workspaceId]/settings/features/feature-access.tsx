'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { Button } from '@/components/ui/button';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
} from '@/components/settings/settings-ui';
import {
  SettingsTableClear,
  SettingsTableHead,
  SettingsTableNoMatch,
  useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import { useWorkspaceStore } from '@/stores/workspace';
// The unsaved-changes bar of the General pages.
import '@/app/organizations/[orgId]/settings/general/general.css';
import { reloadWorkspaceResources } from '@/hooks/use-workspace-resources';
import { PolicyPicker } from '@/components/settings/policy-picker';
import { BulkAccessBar, SelectAllCell, SelectRowCell, useRowSelection } from '@/components/settings/bulk-access';
import { isOrgTarget } from '@/lib/access-model/target';
import { AccessLevelChoice } from '@/components/settings/access-level-choice';
import {
  createAccessLevelsApi,
  type AccessLevel,
  type AccessLevelsApi,
  type LevelsState,
} from '@/lib/access-model/access-levels';
import { createFeatureAccessApi, type FeatureAccessApi } from './feature-access-api';
import {
  FEATURE_COLUMNS,
  FEATURE_EXPORT_HEADERS,
  editsOffer,
  featureCellValues,
  featureExportRow,
  featureSearchTexts,
  levelPlan,
  pickableLevels,
  rowNotes,
  shownLevel,
  sortedRows,
  type FeatureAccessState,
  type FeatureRow,
  featurePage,
  featureDescription,
  type FeatureColumnId,
} from './feature-access-model';

const DEFAULT_API = createFeatureAccessApi();
const DEFAULT_LEVELS_API = createAccessLevelsApi();

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}


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
export function FeatureAccess({
  workspaceId,
  api = DEFAULT_API,
  levelsApi = DEFAULT_LEVELS_API,
  initialPolicy = null,
  onPolicyChange,
  pickerPrefix,
}: {
  workspaceId: string;
  api?: FeatureAccessApi;
  /** Each feature's access level (Read, Write, Admin): a cap in the offer, a grant elsewhere. */
  levelsApi?: AccessLevelsApi;
  /** The policy edited first (`?policy=`); "<W> access" when null. */
  initialPolicy?: string | null;
  /** Told when another policy is picked (null: "<W> access"), e.g. to keep it in the URL. */
  onPolicyChange?: (policyId: string | null) => void;
  /** Before the Policy dropdown, in its row: Platform settings' Organization picker. */
  pickerPrefix?: ReactNode;
}) {
  const [policyId, setPolicyId] = useState<string | null>(initialPolicy);
  const [state, setState] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [levels, setLevels] = useState<LevelsState | null>(null);
  const [levelsFailed, setLevelsFailed] = useState(false);
  // The level picked for each feature: None takes it out, any other level puts it in.
  const [accessDrafts, setAccessDrafts] = useState<Record<string, AccessLevel>>({});

  const load = useCallback(async () => {
    // The levels follow, never holding the table back; without them the table shows who uses
    // each feature, read-only.
    void levelsApi.read(workspaceId, 'feature', policyId).then(
      (read) => {
        setLevels(read);
        setLevelsFailed(false);
      },
      () => {
        setLevels(null);
        setLevelsFailed(true);
      }
    );
    try {
      setState(await api.read(workspaceId, policyId));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read who uses the features.'));
    }
  }, [api, levelsApi, workspaceId, policyId]);

  useEffect(() => {
    setState(null);
    setLevels(null);
    setLevelsFailed(false);
    setAccessDrafts({});
    setRowErrors({});
    void load();
  }, [load]);

  const levelRow = (key: string) => levels?.rows.find((r) => r.name === key) ?? null;
  const savedLevel = (key: string): AccessLevel | null => levelRow(key)?.level ?? null;
  /** What a row shows: the level picked, or None for a feature taken out, or its stored level. */
  const shownOf = (row: FeatureRow): AccessLevel | null =>
    accessDrafts[row.key] ?? shownLevel(row.choice, savedLevel(row.key));

  // Organization › Access: "<O> access", the ceiling of every workspace of the organization.
  const org = isOrgTarget(workspaceId);
  // By name first: rows that tie on the sorted column stay A to Z. A feature the ceiling above
  // does not offer (or denies) is not shown, unless the policy edited still allows it; on
  // "<O> access" itself every feature is, it is where they are taken out.
  const rows = useMemo(
    () =>
      sortedRows(state?.features ?? []).filter(
        (row) => row.offered || row.choice === 'everyone' || (org && editsOffer(state))
      ),
    [state, org]
  );
  const offer = editsOffer(state);
  const columns = FEATURE_COLUMNS;
  const table = useSettingsTable({
    rows,
    columns,
    cellValues: (row: FeatureRow, column: FeatureColumnId) => featureCellValues(row, column, savedLevel(row.key)),
    searchTexts: featureSearchTexts,
    initialSort: 'feature',
  });
  const shown = table.shown;

  const unsavedCount = Object.keys(accessDrafts).length;
  // Rows checked for a batch change of access (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => shown.map((row) => row.key), [shown]));

  // A pick back to what the row holds is no change.
  const pickLevel = (row: FeatureRow, level: AccessLevel) =>
    setAccessDrafts((current) => {
      const { [row.key]: _dropped, ...rest } = current;
      return level === shownLevel(row.choice, savedLevel(row.key)) ? rest : { ...rest, [row.key]: level };
    });

  /** The selected rows `level` fits (a feature the ceiling does not offer only takes None). */
  const bulkPicks = (level: AccessLevel): FeatureRow[] =>
    rows.filter((row) => {
      if (!selection.selected.has(row.key)) return false;
      const lr = levelRow(row.key);
      return !!lr && pickableLevels(row, lr.choices, offer).includes(level);
    });

  /** Set the selected rows to `level`, with the page's other picks, in one save. */
  const applyBulk = async (level: AccessLevel) => {
    const drafts = { ...accessDrafts };
    for (const row of bulkPicks(level)) {
      if (level === shownLevel(row.choice, savedLevel(row.key))) delete drafts[row.key];
      else drafts[row.key] = level;
    }
    setAccessDrafts(drafts);
    await save(drafts);
  };

  /** Save the picks (`drafts`, the page's by default): a batch change saves its own at once. */
  const save = async (drafts: Record<string, AccessLevel> = accessDrafts) => {
    const plan = levelPlan(rows, drafts, savedLevel);
    setSaving(true);
    try {
      // Whether each feature is in (None takes it out), then how far people go with it.
      let refused: Record<string, string> = {};
      if (plan.features.length > 0) {
        const next = await api.save(workspaceId, plan.features, policyId);
        refused = next.errors ?? {};
        setState(next);
        setRowErrors(refused);
        // The nav's pages under Features follow what is offered: a feature taken out (None) drops
        // its settings page at once, not at the next opening of the settings.
        if (editsOffer(next) && !org) {
          void useWorkspaceStore.getState().fetchWorkspaces();
          void reloadWorkspaceResources(workspaceId);
        }
      }
      const wanted = Object.fromEntries(
        Object.entries(plan.levels).filter(([key]) => !refused[key.slice('feature:'.length)])
      );
      if (Object.keys(wanted).length > 0) setLevels(await levelsApi.save(workspaceId, 'feature', wanted, policyId));
      // A refused row keeps its pick, beside why.
      setAccessDrafts(Object.fromEntries(Object.entries(drafts).filter(([key]) => refused[key])));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const discard = () => {
    setAccessDrafts({});
    setRowErrors({});
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(
      FEATURE_EXPORT_HEADERS,
      shown.map((row) => featureExportRow(row, savedLevel(row.key))),
      format,
      `features_${date}`,
      'Features'
    );
  };

  const access = state?.access_policy ?? null;
  const offerHref = access ? ownerHref(access.owner_scope, access.id) : null;
  const edited = state?.policy ?? null;
  const editedHref = edited ? ownerHref(edited.owner_scope, edited.id) : null;
  const pick = (id: string) => {
    const next = access && id === access.id ? null : id;
    setAccessDrafts({});
    setRowErrors({});
    setPolicyId(next);
    onPolicyChange?.(next);
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Features"
        // One value, as Core Services and Modules: how many features.
        badge={state ? `${rows.length} feature${rows.length === 1 ? '' : 's'}` : undefined}
        description={
          !offer && edited ? (
            <>
              What {editedHref ? <Link href={editedHref}>{edited.name}</Link> : edited.name} grants whoever holds it,
              within the workspace&apos;s offer.
            </>
          ) : (
            <>
              What {org ? 'the workspaces of this organization may offer' : 'this workspace offers'}
              {offerHref && access ? (
                <>
                  {' '}
                  (<Link href={offerHref}>{access.name}</Link>)
                </>
              ) : null}
              : None takes a feature out.
            </>
          )
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />
            <Button
              disabled={saving || unsavedCount === 0}
              onClick={() => void save()}
              data-action="save"
            >
              {saving ? 'Saving…' : 'Save'}
            </Button>
          </>
        }
      />

      {/* The policy edited, under the page's words, at its left. */}
      <div className="-mt-3 flex flex-wrap items-center justify-start gap-4" data-policy-picker="">
        {pickerPrefix}
        <PolicyPicker
          policies={state?.policies}
          current={edited ?? access}
          value={edited?.id ?? access?.id}
          onChange={pick}
          disabled={saving || unsavedCount > 0}
        />
      </div>

      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </SettingsNotice>
      )}
      {/* As General: the unsaved changes said in a bar, with Discard changes. */}
      {unsavedCount > 0 || Object.keys(rowErrors).length > 0 ? (
        <div className="org-settings-general-draft" role="status">
          <p className="org-settings-general-draft-text">
            {unsavedCount > 0 ? 'Unsaved changes.' : 'Some changes were refused: see the rows below.'}
          </p>
          <button
            type="button"
            onClick={discard}
            disabled={saving}
            className="org-settings-general-draft-discard"
            data-action="discard"
          >
            Discard changes
          </button>
        </div>
      ) : null}
      {levelsFailed && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          Could not read the access levels: the features cannot be changed. Reload to try again.
        </SettingsNotice>
      )}

      {!state ? (
        !error && <SettingsLoading label="Loading features…" />
      ) : rows.length === 0 ? (
        <SettingsEmpty title="No features." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search feature, description, not offered…"
            // No count nor unsaved line above the search: the bar says what is unsaved.
            meta={<SettingsTableClear table={table} />}
          />
          <BulkAccessBar
            selection={selection}
            noun="feature"
            levels={['none', 'read', 'write', 'admin']}
            onApply={applyBulk}
            skippedFor={(level) => selection.selected.size - bulkPicks(level).length}
            disabled={saving || !levels?.editable}
          />
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={
                  <SelectAllCell
                    selection={selection}
                    keys={shown.map((row) => row.key)}
                    noun="feature"
                    disabled={saving || !levels?.editable}
                  />
                }
                trailing={<th aria-label="Configure" />}
              />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={columns.length + 2} noun="features" />}
                {table.paged.pageRows.map((row) => (
                    <tr key={row.key} data-feature={row.key} className="align-top">
                      <SelectRowCell
                        selection={selection}
                        rowKey={row.key}
                        label={row.label}
                        disabled={saving || !row.editable || !levelRow(row.key) || !levels?.editable}
                      />
                      <td>
                        <p className="font-medium text-foreground">{row.label}</p>
                        <p className="text-xs text-muted-foreground">{row.key}</p>
                      </td>
                      <td data-field="description" className="text-muted-foreground">
                        {featureDescription(row.key) || '—'}
                      </td>
                      <td data-field="access">
                        {(() => {
                          const level = levelRow(row.key);
                          const value = shownOf(row);
                          return level && levels && value ? (
                            <AccessLevelChoice
                              row={level}
                              value={value}
                              mode={levels.mode}
                              allowed={pickableLevels(row, level.choices, offer)}
                              disabled={!levels.editable || saving}
                              onChange={(next) => pickLevel(row, next)}
                            />
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          );
                        })()}
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
                      <td className="whitespace-nowrap text-right">
                        {(() => {
                          const href = org ? null : featurePage(workspaceId, row.key);
                          return href ? (
                            <Link href={href} className="text-xs text-primary hover:underline" data-action="configure">
                              Configure {row.label} →
                            </Link>
                          ) : null;
                        })()}
                      </td>
                    </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <TablePager total={shown.length} paged={table.paged} />
    </div>
  );
}
