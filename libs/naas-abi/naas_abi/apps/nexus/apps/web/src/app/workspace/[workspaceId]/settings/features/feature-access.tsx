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
import { createFeatureAccessApi, type FeatureAccessApi } from './feature-access-api';
import {
  FEATURE_COLUMNS,
  FEATURE_EXPORT_HEADERS,
  changesFrom,
  choicesOf,
  draftOf,
  editsOffer,
  featureCellValues,
  featureColumns,
  featureExportRow,
  featureSearchTexts,
  otherPolicies,
  rowNotes,
  sortedRows,
  type FeatureAccessState,
  type FeatureChoice,
  type FeatureColumnId,
  type FeatureDraft,
  type FeatureRow,
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
export function FeatureAccess({
  workspaceId,
  api = DEFAULT_API,
  initialPolicy = null,
  onPolicyChange,
}: {
  workspaceId: string;
  api?: FeatureAccessApi;
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

  const load = useCallback(async () => {
    try {
      setState(await api.read(workspaceId, policyId));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read who uses the features.'));
    }
  }, [api, workspaceId, policyId]);

  useEffect(() => {
    setState(null);
    setDrafts({});
    setRowErrors({});
    void load();
  }, [load]);

  // By name first: rows that tie on the sorted column stay A to Z.
  const rows = useMemo(
    () => sortedRows(state?.features ?? []).filter((row) => row.key !== FILES_FEATURE),
    [state]
  );
  const offer = editsOffer(state);
  const columns = useMemo(() => featureColumns(offer), [offer]);
  const table = useSettingsTable({
    rows,
    columns,
    cellValues: (row: FeatureRow, column: FeatureColumnId) => featureCellValues(row, column, offer),
    searchTexts: featureSearchTexts,
    initialSort: 'feature',
  });
  const shown = table.shown;

  const draftFor = (row: FeatureRow) => drafts[row.key] ?? draftOf(row);
  const changes = changesFrom(rows, drafts);

  const choose = (row: FeatureRow, choice: FeatureChoice) =>
    setDrafts((current): Record<string, FeatureDraft> => ({ ...current, [row.key]: { choice } }));

  const save = async () => {
    setSaving(true);
    try {
      const next = await api.save(workspaceId, changes, policyId);
      const refused = next.errors ?? {};
      setState(next);
      setRowErrors(refused);
      setDrafts((current) => Object.fromEntries(Object.entries(current).filter(([key]) => refused[key])));
      setError('');
      // The nav's pages under Features follow what is offered.
      if (editsOffer(next)) void useWorkspaceStore.getState().fetchWorkspaces();
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
    setRowErrors({});
    setPolicyId(next);
    onPolicyChange?.(next);
  };
  const unsaved =
    changes.length === 0 ? 'No unsaved change' : `${changes.length} unsaved change${changes.length === 1 ? '' : 's'}`;

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
              within the workspace&apos;s offer{access ? ` (${access.name})` : ''}. Files are in{' '}
              <Link href={`/workspace/${workspaceId}/settings/files`}>Files</Link>.
            </>
          ) : (
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
          )
        }
        actions={
          <>
            <PolicyPicker
              policies={state?.policies}
              value={edited?.id ?? access?.id}
              onChange={pick}
              disabled={saving || changes.length > 0}
            />
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
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search feature, everyone, nobody, policy, not offered…"
            meta={
              <>
                {`${countLabel(shown.length, rows.length, 'feature')} · ${unsaved}`}
                <SettingsTableClear table={table} />
              </>
            }
          />
          <p className="text-xs text-muted-foreground">
            Other policies may grant or deny a feature too, and a Deny always wins.
          </p>
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={columns.length} noun="features" />}
                {table.paged.pageRows.map((row) => {
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
                          {choicesOf(row, offer).map((choice) => (
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
      <TablePager total={shown.length} paged={table.paged} />
    </div>
  );
}
