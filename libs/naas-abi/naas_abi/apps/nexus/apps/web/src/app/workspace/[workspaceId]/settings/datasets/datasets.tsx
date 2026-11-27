'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { Checkbox } from '@/components/ui/checkbox';
import { BulkBar, SelectAllCell, SelectRowCell, onOffActions, useRowSelection } from '@/components/settings/bulk-access';
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
import { isOrgTarget } from '@/lib/access-model/target';
import { createDatasetsOfferApi, type DatasetsOfferApi } from './datasets-api';
import {
  DATASET_COLUMNS,
  DATASET_EXPORT_HEADERS,
  bulkChanges,
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

/** The batch actions: offer the namespaces selected, or take them back. */
const BULK_ACTIONS = onOffActions({ on: 'Offer', off: 'Take back' }, (on) =>
  on ? 'Their datasets come back, in one save.' : 'Their datasets are hidden, agents included, in one save.'
);

/**
 * Settings › Datasets: the dataset namespaces a workspace uses (or, on an organization, that its
 * workspaces may use), laid out as Settings › Users. Unchecking closes a namespace in "<W> access"
 * ("<O> access"); a namespace closed above stays read-only. A table of switches: each change is
 * saved at once, and said; the namespaces selected change together, asked first.
 */
export function DatasetsOffer({
  target,
  policyId = null,
  api = DEFAULT_API,
}: {
  target: string;
  /** The policy picked in the Settings column (`?policy=`); "<W> access" when null. */
  policyId?: string | null;
  api?: DatasetsOfferApi;
}) {
  const [state, setState] = useState<DatasetsState | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.read(target, policyId));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read the datasets.'));
    }
  }, [api, target, policyId]);

  useEffect(() => {
    setState(null);
    setNotice('');
    void load();
  }, [load]);

  const org = isOrgTarget(target);
  const rows = useMemo(() => state?.rows ?? [], [state]);
  const table = useSettingsTable({
    rows,
    columns: DATASET_COLUMNS,
    cellValues: datasetCellValues,
    sortValue: datasetSortValue,
    searchTexts: datasetSearchTexts,
    initialSort: 'namespace',
  });
  const shown = table.shown;
  // The policy set here: the one picked in the column, else "<W> access".
  const access = state?.policy ?? state?.access_policy ?? null;
  const accessHref = access ? ownerHref(access.owner_scope, access.id) : null;
  // The namespaces checked for a batch change (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => shown.map((row) => row.namespace), [shown]));

  /** One write of the offer for `changes`, then what it did said in `done`. */
  const save = async (changes: Record<string, boolean>, done: string) => {
    if (Object.keys(changes).length === 0) {
      setNotice(done);
      return;
    }
    setSaving(true);
    setNotice('');
    try {
      setState(await api.save(target, changes, policyId));
      setError('');
      setNotice(done);
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const toggle = (row: DatasetRow, on: boolean) =>
    void save({ [row.namespace]: on }, `${row.namespace}: ${on ? 'offered' : 'not offered'}.`);

  const applyBulk = async (id: string) => {
    const on = id === 'on';
    const changes = bulkChanges(rows, selection.selected, on);
    const count = Object.keys(changes).length;
    await save(changes, `${count} namespace${count === 1 ? '' : 's'} ${on ? 'offered' : 'taken back'}.`);
  };
  /** The selected namespaces a batch change does not fit: those that cannot change here. */
  const skipped = () => rows.filter((row) => selection.selected.has(row.namespace) && !row.editable).length;

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(DATASET_EXPORT_HEADERS, shown.map(datasetExportRow), format, `datasets_${date}`, 'Datasets');
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Datasets"
        // One total: how many namespaces (the Offered column says which are used).
        badge={state ? `${rows.length} namespace${rows.length === 1 ? '' : 's'}` : undefined}
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
          </>
        }
      />

      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </SettingsNotice>
      )}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-datasets-notice="">
          {notice}
        </p>
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
            // No count above the search: the badge says how many, the pager how many are shown.
            meta={<SettingsTableClear table={table} />}
          />
          <p className="text-xs text-muted-foreground" data-datasets-legend="">
            Unchecking a namespace hides its datasets {org ? 'in every workspace of the organization' : 'in this workspace'},
            agents included. Only the platform admin reopens a namespace closed here.
          </p>
          <BulkBar
            selection={selection}
            noun="namespace"
            actions={BULK_ACTIONS}
            onApply={applyBulk}
            skippedFor={skipped}
            change="this change"
            disabled={saving}
          />
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={
                  <SelectAllCell
                    selection={selection}
                    keys={shown.filter((row) => row.editable).map((row) => row.namespace)}
                    noun="namespace"
                    disabled={saving}
                  />
                }
              />
              <tbody>
                {shown.length === 0 && <SettingsTableNoMatch colSpan={DATASET_COLUMNS.length + 1} noun="namespaces" />}
                {table.paged.pageRows.map((row) => {
                  const on = row.offered;
                  const note = rowNote(row);
                  return (
                    <tr key={row.namespace} data-namespace={row.namespace} className="align-top">
                      <SelectRowCell
                        selection={selection}
                        rowKey={row.namespace}
                        label={row.namespace}
                        disabled={saving || !row.editable}
                      />
                      <td className="font-medium text-foreground">{row.namespace}</td>
                      <td className="tabular-nums text-muted-foreground">{row.tables}</td>
                      <td>
                        <span className="inline-flex items-center gap-2">
                          <Checkbox
                            checked={on}
                            disabled={!row.editable || saving}
                            aria-label={`Offer ${row.namespace}`}
                            data-offered={row.namespace}
                            onCheckedChange={(checked) => toggle(row, checked)}
                          />
                          <span className="text-xs text-muted-foreground">{on ? 'Offered' : 'Not offered'}</span>
                        </span>
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
