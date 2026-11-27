'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Save } from 'lucide-react';
import { usePageDraft } from '@/hooks/use-page-state';
import { SettingsPageHeader, SettingsTableToolbar } from '@/components/settings/settings-ui';
import { Notice } from '@/components/ui/notice';
import { Loading } from '@/components/ui/spinner';
import {
  SettingsTableClear,
  SettingsTableHead,
  SettingsTableNoMatch,
  useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import {
  FILES_COLUMNS,
  FILES_EXPORT_HEADERS,
  filesCellValues,
  filesExportRow,
  filesSearchTexts,
  filesSortValue,
  FILES_DESCRIPTIONS,
  type FilesRow,
} from './files-model';
import {
  createOfferApi,
  type FileMode,
  type FileRow,
  type OfferApi,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import { createFeatureAccessApi, type FeatureAccessApi } from '../features/feature-access-api';
import type { FeatureAccessState, FeatureRow } from '../features/feature-access-model';

// The unsaved-changes bar of the General pages, and their Save button; the Users table.
import '@/app/organizations/[orgId]/settings/general/general.css';
import '@/app/organizations/[orgId]/settings/users/users.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import { usePolicyViewStore } from '@/components/settings/settings-policy-picker';

const DEFAULT_OFFER_API = createOfferApi();
const DEFAULT_FEATURE_API = createFeatureAccessApi();
/** The feature that is the workspace's own files (Workspace Files). */
export const FILES_FEATURE = 'files';

const MODE_LABELS: Record<FileMode, string> = { off: 'Off', read: 'Read', write: 'Read and write' };
const MODE_HINTS: Record<FileMode, string> = {
  off: 'The people of this workspace do not get these files from it',
  read: 'They list and read these files',
  write: 'Members also write and delete them; Viewers read them',
};

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * Settings › Files: every kind of files the people of a workspace open, in one place, each within their
 * level. Workspace Files is the workspace's `files` feature (Everyone or Nobody); Organization, Platform
 * and System Files are the given sections of its offer (Off, Read, Read and write; System Files Off or
 * Read); My Files is a setting of the deployment, shown. A form: the choices wait for Save (faded until
 * something changes), the unsaved bar says so, and they are kept for a return to the page
 * (`usePageDraft`); Save writes them through IAM as the caller: a choice they may not give is
 * disabled, with why.
 */
export function WorkspaceFiles({
  workspaceId,
  offerApi = DEFAULT_OFFER_API,
  featureApi = DEFAULT_FEATURE_API,
  description,
  policyId = null,
}: {
  workspaceId: string;
  /** The policy picked in the Settings column (`?policy=`); "<W> access" when null. */
  policyId?: string | null;
  offerApi?: OfferApi;
  featureApi?: FeatureAccessApi;
  /** The page's line under its title. */
  description?: string;
}) {
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [features, setFeatures] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const [nextOffer, nextFeatures] = await Promise.all([
        offerApi.read(workspaceId, policyId),
        featureApi.read(workspaceId, policyId).catch(() => null),
      ]);
      setOffer(nextOffer);
      setFeatures(nextFeatures);
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read the files of this workspace.'));
    }
  }, [offerApi, featureApi, workspaceId, policyId]);

  useEffect(() => {
    setOffer(null);
    setFeatures(null);
    void load();
  }, [load]);

  const workspaceFiles: FeatureRow | null = features?.features.find((row) => row.key === FILES_FEATURE) ?? null;

  // What the workspace holds (`workspace`: Workspace Files, Everyone or Nobody; a mode per section
  // of files), and the choices made over it, kept for a return to the page.
  const server = useMemo(() => {
    if (!offer) return null;
    const record: Record<string, string> = Object.fromEntries((offer.files ?? []).map((row) => [row.key, row.mode]));
    if (workspaceFiles) record.workspace = workspaceFiles.choice === 'everyone' ? 'everyone' : 'nobody';
    return record;
  }, [offer, workspaceFiles]);
  const draft = usePageDraft(
    workspaceId ? { scope: `workspace:${workspaceId}`, page: 'files', detail: policyId ?? undefined } : null,
    server
  );
  const values = useMemo(() => draft.values ?? server ?? {}, [draft.values, server]);
  const changed = Object.keys(values).filter((key) => server && values[key] !== server[key]);
  const dirty = changed.length > 0;
  const workspaceFilesOn = values.workspace === 'everyone';

  const choose = (key: string, value: string) => {
    setSaved(false);
    draft.set({ [key]: value });
  };

  /** Save: Workspace Files through the feature, then the sections of files in one write of the offer. */
  const save = async () => {
    setSaving(true);
    setError('');
    try {
      if (changed.includes('workspace') && workspaceFiles) {
        const next = await featureApi.save(
          workspaceId,
          [{ feature: FILES_FEATURE, choice: workspaceFilesOn ? 'everyone' : 'nobody' }],
          policyId
        );
        setFeatures(next);
        // The column's Features group follows what the policy grants: read again.
        usePolicyViewStore.getState().forget(workspaceId);
        const refused = next.errors?.[FILES_FEATURE];
        if (refused) throw new Error(refused);
      }
      const modes = Object.fromEntries(changed.filter((key) => key !== 'workspace').map((key) => [key, values[key]]));
      if (Object.keys(modes).length > 0) {
        setOffer(await offerApi.saveFiles(workspaceId, modes as Partial<Record<FileRow['key'], FileMode>>, policyId));
      }
      draft.discard();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  // One row per kind of files, in the page's order: Workspace, the sections of the offer, My Files.
  const rows: FilesRow[] = useMemo(() => {
    if (!offer) return [];
    const list: FilesRow[] = [
      {
        key: 'workspace',
        label: 'Workspace Files',
        description: workspaceFiles ? "The workspace's own files" : 'The Files feature is not enabled on this deployment',
        value: workspaceFiles ? (values.workspace ?? null) : null,
        choices: workspaceFiles
          ? [
              { value: 'everyone', label: 'Everyone' },
              { value: 'nobody', label: 'Nobody' },
            ]
          : [],
        editable: !!workspaceFiles?.editable,
        reason: workspaceFiles && !workspaceFiles.editable ? workspaceFiles.reason : null,
        order: 0,
      },
      ...(offer.files ?? []).map((row, index) => ({
        key: row.key,
        label: row.label,
        description: FILES_DESCRIPTIONS[row.key] ?? `${row.label}, given to this workspace`,
        value: values[row.key] ?? null,
        choices: row.modes.map((mode) => ({
          value: mode,
          label: MODE_LABELS[mode],
          hint: MODE_HINTS[mode],
          disabled: !row.choices.includes(mode),
        })),
        editable: row.editable,
        reason: row.editable ? null : row.reason,
        order: index + 1,
      })),
    ];
    if (offer.my_files) {
      list.push({
        key: 'my_files',
        label: 'My Files',
        description: `Every Member writes theirs; Viewers ${
          offer.my_files.viewers === 'read' ? 'read theirs' : 'have none'
        }. A setting of the deployment, not of the workspace`,
        value: null,
        choices: [],
        editable: false,
        reason: null,
        order: list.length,
      });
    }
    return list;
  }, [offer, workspaceFiles, values]);
  const table = useSettingsTable({
    rows,
    columns: FILES_COLUMNS,
    cellValues: filesCellValues,
    sortValue: filesSortValue,
    searchTexts: filesSearchTexts,
    initialSort: 'files',
  });
  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(FILES_EXPORT_HEADERS, table.shown.map(filesExportRow), format, `files_${date}`, 'Files');
  };

  // One total: the kinds of files listed (Workspace, Organization, Platform, System, My Files).
  const kinds = offer ? rows.length : null;

  return (
    <>
    <SettingsPageHeader
      title="Files"
      badge={kinds === null ? undefined : `${kinds} kind${kinds === 1 ? '' : 's'} of files`}
      description={description}
      actions={
        <>
        <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
        {/* The button of the General pages: faded until something changes. */}
        <button
          type="button"
          onClick={() => void save()}
          disabled={!dirty || saving}
          data-action="save"
          className={saved ? 'org-settings-primary-button org-settings-primary-button-saved' : 'org-settings-primary-button'}
        >
          <Save size={16} />
          {saved ? 'Saved!' : saving ? 'Saving...' : 'Save changes'}
        </button>
        </>
      }
    />
    {error && <Notice tone="error">{error}</Notice>}
    {dirty ? (
      <div className="org-settings-general-draft" role="status">
        <p className="org-settings-general-draft-text">
          {draft.conflicts.length > 0 ? 'Changed elsewhere since you began editing: saving keeps your choices.' : 'Unsaved changes.'}
        </p>
        <button
          type="button"
          onClick={() => {
            draft.discard();
            setError('');
          }}
          disabled={saving}
          className="org-settings-general-draft-discard"
        >
          Discard changes
        </button>
      </div>
    ) : null}
    {!offer ? (
      !error && <Loading label="Loading files…" />
    ) : (
      <div className="space-y-4">
        <SettingsTableToolbar
          search={table.search}
          onSearchChange={table.setSearch}
          searchPlaceholder="Search files, access…"
          meta={<SettingsTableClear table={table} />}
        />
        <div className="org-settings-users-table-wrap">
          <table className="org-settings-users-table">
            <SettingsTableHead table={table} />
            <tbody>
              {table.shown.length === 0 && <SettingsTableNoMatch colSpan={FILES_COLUMNS.length} noun="files" />}
              {table.paged.pageRows.map((row) => (
                <tr key={row.key} data-files={row.key} className="align-top">
                  <td>
                    <p className="font-medium text-foreground">{row.label}</p>
                    <p className="text-xs text-muted-foreground">{row.description}</p>
                  </td>
                  <td data-field="access">
                    {row.choices.length > 0 ? (
                      <>
                        <div className="workspace-features-choices" role="radiogroup" aria-label={row.label}>
                          {row.choices.map((choice) => (
                            <button
                              key={choice.value}
                              type="button"
                              role="radio"
                              aria-checked={row.value === choice.value}
                              data-choice={choice.value}
                              title={choice.hint}
                              disabled={!row.editable || choice.disabled || saving}
                              className="workspace-features-choice"
                              onClick={() => choose(row.key, choice.value)}
                            >
                              {choice.label}
                            </button>
                          ))}
                        </div>
                        {row.reason && <p className="workspace-features-note">{row.reason}</p>}
                      </>
                    ) : (
                      <span className="text-xs text-muted-foreground">Set by the deployment</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <TablePager total={table.shown.length} paged={table.paged} />
      </div>
    )}
    </>
  );
}
