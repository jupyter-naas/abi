'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { Button } from '@/components/ui/button';
import {
  SettingsEmpty,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsTableToolbar,
  countLabel,
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
import { PolicyPicker } from '@/components/settings/policy-picker';
import { isOrgTarget } from '@/lib/access-model/target';
import { AccessLevelChoice } from '@/components/settings/access-level-choice';
import {
  LEVEL_LABELS,
  createAccessLevelsApi,
  type AccessLevel,
  type AccessLevelsApi,
  type LevelsState,
} from '@/lib/access-model/access-levels';
import { createFeatureAccessApi, type FeatureAccessApi } from './feature-access-api';
import {
  FEATURE_COLUMNS,
  FEATURE_EXPORT_HEADERS,
  changesFrom,
  choicesOf,
  draftOf,
  editsOffer,
  featureCellValues,
  featureExportRow,
  featureSearchTexts,
  rowNotes,
  sortedRows,
  type FeatureAccessState,
  type FeatureChoice,
  type FeatureDraft,
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
}: {
  workspaceId: string;
  api?: FeatureAccessApi;
  /** Each feature's access level (Read, Write, Admin): a cap in the offer, a grant elsewhere. */
  levelsApi?: AccessLevelsApi;
  /** The policy edited first (`?policy=`); "<W> access" when null. */
  initialPolicy?: string | null;
  /** Told when another policy is picked (null: "<W> access"), e.g. to keep it in the URL. */
  onPolicyChange?: (policyId: string | null) => void;
}) {
  const [policyId, setPolicyId] = useState<string | null>(initialPolicy);
  const [state, setState] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [drafts, setDrafts] = useState<Record<string, FeatureDraft>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [levels, setLevels] = useState<LevelsState | null>(null);
  const [accessDrafts, setAccessDrafts] = useState<Record<string, AccessLevel>>({});

  const load = useCallback(async () => {
    // The levels follow, never holding the table back; without them it still shows who uses
    // each feature.
    void levelsApi.read(workspaceId, 'feature', policyId).then(setLevels, () => setLevels(null));
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
    setDrafts({});
    setAccessDrafts({});
    setRowErrors({});
    void load();
  }, [load]);

  const levelRow = (key: string) => levels?.rows.find((r) => r.name === key) ?? null;
  const levelOf = (key: string): AccessLevel | null => accessDrafts[key] ?? levelRow(key)?.level ?? null;

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
    cellValues: (row: FeatureRow, column: FeatureColumnId) => {
      if (column !== 'access') return featureCellValues(row, column);
      const level = levelRow(row.key)?.level;
      return level ? [LEVEL_LABELS[level]] : [];
    },
    searchTexts: featureSearchTexts,
    initialSort: 'feature',
  });
  const shown = table.shown;

  const draftFor = (row: FeatureRow) => drafts[row.key] ?? draftOf(row);
  const changes = changesFrom(rows, drafts);
  const accessChanges = Object.entries(accessDrafts).filter(([key, level]) => level !== levelRow(key)?.level);
  const unsavedCount = changes.length + accessChanges.length;

  const choose = (row: FeatureRow, choice: FeatureChoice) =>
    setDrafts((current): Record<string, FeatureDraft> => ({ ...current, [row.key]: { choice } }));

  const save = async () => {
    setSaving(true);
    try {
      if (changes.length > 0) {
        const next = await api.save(workspaceId, changes, policyId);
        const refused = next.errors ?? {};
        setState(next);
        setRowErrors(refused);
        setDrafts((current) => Object.fromEntries(Object.entries(current).filter(([key]) => refused[key])));
        // The nav's pages under Features follow what is offered.
        if (editsOffer(next) && !org) void useWorkspaceStore.getState().fetchWorkspaces();
      }
      if (accessChanges.length > 0) {
        const wanted = Object.fromEntries(accessChanges.map(([key, level]) => [`feature:${key}`, level]));
        setLevels(await levelsApi.save(workspaceId, 'feature', wanted, policyId));
        setAccessDrafts({});
      }
      setError('');
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const discard = () => {
    setDrafts({});
    setAccessDrafts({});
    setRowErrors({});
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(FEATURE_EXPORT_HEADERS, shown.map(featureExportRow), format, `features_${date}`, 'Features');
  };

  const access = state?.access_policy ?? null;
  const offerHref = access ? ownerHref(access.owner_scope, access.id) : null;
  const edited = state?.policy ?? null;
  const editedHref = edited ? ownerHref(edited.owner_scope, edited.id) : null;
  const offeredCount = rows.filter((row) => row.choice === 'everyone').length;
  const pick = (id: string) => {
    const next = access && id === access.id ? null : id;
    setDrafts({});
    setAccessDrafts({});
    setRowErrors({});
    setPolicyId(next);
    onPolicyChange?.(next);
  };
  const unsaved =
    unsavedCount === 0 ? 'No unsaved change' : `${unsavedCount} unsaved change${unsavedCount === 1 ? '' : 's'}`;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Features"
        badge={
          state
            ? offer
              ? `${offeredCount} offered · ${rows.length - offeredCount} not offered`
              : `${offeredCount} granted · ${rows.length - offeredCount} not granted`
            : undefined
        }
        description={
          !offer && edited ? (
            <>
              What{' '}
              {editedHref ? <Link href={editedHref}>{edited.name}</Link> : edited.name} grants whoever holds it,
              within the workspace&apos;s offer{access ? ` (${access.name})` : ''}. The files given from outside the
              workspace are in <Link href={`/workspace/${workspaceId}/settings/files`}>Files</Link>.
            </>
          ) : org ? (
          <>
            Whether the workspaces of this organization may offer each feature (Enabled), and how far people go with
            it there (Access): a ceiling for every one of them, admins included
            {offerHref && access ? (
              <>
                {' '}
                (<Link href={offerHref}>{access.name}</Link>)
              </>
            ) : null}
            . A workspace never offers what is not enabled here.
          </>
          ) : (
          <>
            Whether this workspace offers each feature (Enabled), and how far people go with it (Access). Each
            person&apos;s level decides what they may do with it, admins included. Part of what the workspace offers
            {offerHref && access ? (
              <>
                {' '}
                (<Link href={offerHref}>{access.name}</Link>)
              </>
            ) : null}
            ; the files given from outside the workspace (Organization, Platform, System) are in{' '}
            <Link href={`/workspace/${workspaceId}/settings/files`}>Files</Link>.
          </>
          )
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />
            <Button
              variant="secondary"
              data-action="discard"
              disabled={saving || (unsavedCount === 0 && Object.keys(rowErrors).length === 0)}
              onClick={discard}
            >
              Discard
            </Button>
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
      <div className="-mt-3 flex justify-start" data-policy-picker="">
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

      {!state ? (
        !error && <SettingsLoading label="Loading features…" />
      ) : rows.length === 0 ? (
        <SettingsEmpty title="No features." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search feature, description, enabled, not offered…"
            meta={
              <>
                {`${countLabel(shown.length, rows.length, 'feature')} · ${unsaved}`}
                <SettingsTableClear table={table} />
              </>
            }
          />
          <p className="text-xs text-muted-foreground" data-access-legend="">
            <strong>Access</strong>: how far people go with an enabled feature. Read lets them see it, Write also
            create and change, Admin also configure it.{' '}
            {offer
              ? org
                ? 'Here it is a cap for every workspace of the organization, admins included.'
                : 'Here it is a cap for everyone in the workspace, admins included; each person’s level still applies below it.'
              : 'Here it is what this policy grants whoever holds it, within the workspace’s offer.'}{' '}
            Unfold Actions to see what each level allows.
          </p>
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} trailing={<th aria-label="Configure" />} />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={columns.length + 1} noun="features" />}
                {table.paged.pageRows.map((row) => {
                  const draft = draftFor(row);
                  return (
                    <tr key={row.key} data-feature={row.key} className="align-top">
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
                          const value = levelOf(row.key);
                          return level && levels && value ? (
                            <AccessLevelChoice
                              row={level}
                              value={value}
                              mode={levels.mode}
                              disabled={!levels.editable || saving}
                              onChange={(next) => setAccessDrafts((current) => ({ ...current, [row.key]: next }))}
                            />
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          );
                        })()}
                      </td>
                      <td data-field="enabled">
                        {(() => {
                          const on = draft.choice === 'everyone';
                          const choices = choicesOf(row, offer);
                          const can = choices.find((c) => c.value === (on ? 'nobody' : 'everyone'))?.enabled ?? false;
                          const hint = choices.find((c) => c.value === 'everyone')?.hint;
                          return (
                            <label className="inline-flex items-center gap-2" title={hint}>
                              <input
                                type="checkbox"
                                checked={on}
                                disabled={!can || saving}
                                aria-label={`${offer ? 'Offer' : 'Grant'} ${row.label}`}
                                data-enabled={row.key}
                                onChange={(event) => choose(row, event.target.checked ? 'everyone' : 'nobody')}
                              />
                              <span className="text-xs text-muted-foreground">{on ? 'Enabled' : 'Disabled'}</span>
                            </label>
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
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <TablePager total={shown.length} paged={table.paged} />
    </div>
  );
}
