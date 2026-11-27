'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
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
import { isOrgTarget } from '@/lib/access-model/target';
import { createDatasetsOfferApi, type DatasetsOfferApi } from './datasets-api';
import {
  DATASET_COLUMNS,
  DATASET_EXPORT_HEADERS,
  changesFrom,
  datasetCellValues,
  datasetExportRow,
  datasetSearchTexts,
  datasetSortValue,
  rowNote,
  type DatasetRow,
  type DatasetsState,
} from './datasets-model';

const DEFAULT_API = createDatasetsOfferApi();

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/**
 * Settings › Datasets: the dataset namespaces a workspace uses (or, on an organization, that its
 * workspaces may use), laid out as Settings › Users. Unchecking closes a namespace in "<W> access"
 * ("<O> access"); a namespace closed above stays read-only.
 */
export function DatasetsOffer({ target, api = DEFAULT_API }: { target: string; api?: DatasetsOfferApi }) {
  const [state, setState] = useState<DatasetsState | null>(null);
  const [error, setError] = useState('');
  const [drafts, setDrafts] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.read(target));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read the datasets.'));
    }
  }, [api, target]);

  useEffect(() => {
    setState(null);
    setDrafts({});
    void load();
  }, [load]);

  const org = isOrgTarget(target);
  const rows = state?.rows ?? [];
  const table = useSettingsTable({
    rows,
    columns: DATASET_COLUMNS,
    cellValues: datasetCellValues,
    sortValue: datasetSortValue,
    searchTexts: datasetSearchTexts,
    initialSort: 'namespace',
  });
  const shown = table.shown;
  const changes = changesFrom(rows, drafts);
  const unsavedCount = Object.keys(changes).length;
  const offeredCount = rows.filter((row) => row.offered).length;
  const access = state?.access_policy ?? null;
  const accessHref = access ? ownerHref(access.owner_scope, access.id) : null;

  const toggle = (row: DatasetRow, on: boolean) =>
    setDrafts((current) => {
      const { [row.namespace]: _dropped, ...rest } = current;
      return on === row.offered ? rest : { ...rest, [row.namespace]: on };
    });

  const save = async () => {
    setSaving(true);
    try {
      setState(await api.save(target, changes));
      setDrafts({});
      setError('');
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(DATASET_EXPORT_HEADERS, shown.map(datasetExportRow), format, `datasets_${date}`, 'Datasets');
  };

  const unsaved =
    unsavedCount === 0 ? 'No unsaved change' : `${unsavedCount} unsaved change${unsavedCount === 1 ? '' : 's'}`;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Datasets"
        badge={state ? `${offeredCount} offered · ${rows.length - offeredCount} not offered` : undefined}
        description={
          <>
            The dataset namespaces {org ? 'the workspaces of this organization may use' : 'this workspace uses'}
            {accessHref && access ? (
              <>
                {' '}
                (<Link href={accessHref}>{access.name}</Link>)
              </>
            ) : null}
            .
          </>
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={shown.length === 0} />
            <Button
              variant="secondary"
              data-action="discard"
              disabled={saving || unsavedCount === 0}
              onClick={() => setDrafts({})}
            >
              Discard
            </Button>
            <Button disabled={saving || unsavedCount === 0} onClick={() => void save()} data-action="save">
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
      {state?.error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {state.error}
        </SettingsNotice>
      )}

      {!state ? (
        !error && <SettingsLoading label="Loading datasets…" />
      ) : rows.length === 0 ? (
        <SettingsEmpty title="No dataset namespace." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search namespace, offered, not offered…"
            meta={
              <>
                {`${countLabel(shown.length, rows.length, 'namespace')} · ${unsaved}`}
                <SettingsTableClear table={table} />
              </>
            }
          />
          <p className="text-xs text-muted-foreground" data-datasets-legend="">
            Unchecking a namespace hides its datasets {org ? 'in every workspace of the organization' : 'in this workspace'},
            agents included. Only the platform admin reopens a namespace closed here.
          </p>
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={DATASET_COLUMNS.length} noun="namespaces" />}
                {table.paged.pageRows.map((row) => {
                  const on = drafts[row.namespace] ?? row.offered;
                  const note = rowNote(row);
                  return (
                    <tr key={row.namespace} data-namespace={row.namespace} className="align-top">
                      <td className="font-medium text-foreground">{row.namespace}</td>
                      <td className="tabular-nums text-muted-foreground">{row.tables}</td>
                      <td>
                        <label className="inline-flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={on}
                            disabled={!row.editable || saving}
                            aria-label={`Offer ${row.namespace}`}
                            data-offered={row.namespace}
                            onChange={(event) => toggle(row, event.target.checked)}
                          />
                          <span className="text-xs text-muted-foreground">{on ? 'Offered' : 'Not offered'}</span>
                        </label>
                        {note ? <p className="workspace-features-note">{note}</p> : null}
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
