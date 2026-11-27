'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { ownerHref } from '@/components/access/policies/policy-owners';
import { AccessLevelChoice } from '@/components/settings/access-level-choice';
import { BulkAccessBar, SelectAllCell, SelectRowCell, useRowSelection } from '@/components/settings/bulk-access';
import { PolicyPicker } from '@/components/settings/policy-picker';
import { isOrgTarget } from '@/lib/access-model/target';
import { SettingsPageHeader, SettingsTableToolbar } from '@/components/settings/settings-ui';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import { Notice } from '@/components/ui/notice';
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
  LEVEL_LABELS,
  createAccessLevelsApi,
  type AccessLevel,
  type AccessLevelsApi,
  type LevelRow,
  type LevelsState,
} from '@/lib/access-model/access-levels';
import {
  SERVICE_COLUMNS,
  SERVICE_EXPORT_HEADERS,
  serviceCellValues,
  serviceExportRow,
  serviceSearchTexts,
} from './core-services-model';

const DEFAULT_API = createAccessLevelsApi();

const message = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

/**
 * Settings › Access › Services: how far people go with each core service of the engine (the
 * triple store's graphs, object storage, vector store, datasets, documents, secrets...) in the
 * workspace, apart from the Nexus features (Access › Features). A policy picked in the header:
 * "<W> access" caps it for everyone in the workspace, admins included (Denies above the level);
 * another policy grants it to its holders (Allows up to the level). Each change is saved at once,
 * as the caller.
 */
export function CoreServices({
  workspaceId,
  api = DEFAULT_API,
  initialPolicy = null,
  onPolicyChange,
  pickerPrefix,
}: {
  workspaceId: string;
  api?: AccessLevelsApi;
  initialPolicy?: string | null;
  onPolicyChange?: (policyId: string | null) => void;
  /** Before the Policy dropdown, in its row: Platform settings' Organization picker. */
  pickerPrefix?: ReactNode;
}) {
  const [policyId, setPolicyId] = useState<string | null>(initialPolicy);
  const [state, setState] = useState<LevelsState | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.read(workspaceId, 'service', policyId));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read the core services.'));
    }
  }, [api, workspaceId, policyId]);

  useEffect(() => {
    setState(null);
    setNotice('');
    void load();
  }, [load]);

  const rows = state?.rows ?? [];
  const table = useSettingsTable({
    rows,
    columns: SERVICE_COLUMNS,
    cellValues: serviceCellValues,
    searchTexts: serviceSearchTexts,
    initialSort: 'service',
  });

  // Rows checked for a batch change of access (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => table.shown.map((row) => row.key), [table.shown]));
  /** The selected rows `level` fits (a service has the levels its actions have). */
  const bulkRows = (level: AccessLevel) =>
    rows.filter((row) => selection.selected.has(row.key) && row.choices.includes(level));

  /** Every selected row `level` fits, in one save. */
  const applyBulk = async (level: AccessLevel) => {
    const changes = Object.fromEntries(bulkRows(level).filter((row) => row.level !== level).map((row) => [row.key, level]));
    if (Object.keys(changes).length === 0) return;
    setSaving(true);
    setNotice('');
    try {
      const next = await api.save(workspaceId, 'service', changes, policyId);
      setState(next);
      setError('');
      const n = Object.keys(changes).length;
      setNotice(`${n} service${n === 1 ? '' : 's'}: ${LEVEL_LABELS[level]}.`);
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const change = async (row: LevelRow, level: AccessLevel) => {
    setSaving(true);
    setNotice('');
    try {
      const next = await api.save(workspaceId, 'service', { [row.key]: level }, policyId);
      setState(next);
      setError('');
      setNotice(`${row.label}: ${LEVEL_LABELS[level]}.`);
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(SERVICE_EXPORT_HEADERS, table.shown.map(serviceExportRow), format, `services_${date}`, 'Services');
  };

  const access = state?.access_policy ?? null;
  const edited = state?.policy ?? access;
  const editedHref = edited ? ownerHref(edited.owner_scope, edited.id) : null;
  const cap = state?.mode !== 'grant';
  const pick = (id: string) => {
    const next = access && id === access.id ? null : id;
    setPolicyId(next);
    onPolicyChange?.(next);
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Core Services"
        badge={state ? `${rows.length} service${rows.length === 1 ? '' : 's'}` : undefined}
        description={
          cap && isOrgTarget(workspaceId) ? (
            'How far people go with each engine service in every workspace of this organization, admins included'
          ) : cap ? (
            'How far everyone here goes with each engine service, admins included; each person’s level applies below'
          ) : (
            <>
              What {editedHref && edited ? <Link href={editedHref}>{edited.name}</Link> : edited?.name} grants whoever holds it
              of each core service, up to a level, within the workspace&apos;s offer{access ? ` (${access.name})` : ''}.
            </>
          )
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
          </>
        }
      />

      {/* The policy edited, under the page's words, at its left. */}
      <div className="-mt-3 flex flex-wrap items-center justify-start gap-4" data-policy-picker="">
        {pickerPrefix}
        <PolicyPicker policies={state?.policies} current={edited} value={edited?.id} onChange={pick} disabled={saving} />
      </div>

      {error && (
        <Notice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </Notice>
      )}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-services-notice="">
          {notice}
        </p>
      )}
      {state && !state.editable && state.reason && <Notice tone="info">{state.reason}</Notice>}

      {!state ? (
        !error && <Loading label="Loading services…" />
      ) : rows.length === 0 ? (
        <EmptyState framed title="No core service has levels here." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search service, level, action…"
            meta={<SettingsTableClear table={table} />}
          />
          <BulkAccessBar
            selection={selection}
            noun="service"
            levels={['none', 'read', 'write', 'admin']}
            onApply={applyBulk}
            skippedFor={(level) => selection.selected.size - bulkRows(level).length}
            disabled={saving || !state.editable}
          />
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={
                  <SelectAllCell
                    selection={selection}
                    keys={table.shown.map((row) => row.key)}
                    noun="service"
                    disabled={saving || !state.editable}
                  />
                }
              />
              <tbody>
                {table.shown.length === 0 && <SettingsTableNoMatch colSpan={SERVICE_COLUMNS.length + 1} noun="services" />}
                {table.paged.pageRows.map((row) => (
                  <tr key={row.key} data-service={row.name} className="align-top">
                    <SelectRowCell selection={selection} rowKey={row.key} label={row.label} disabled={saving || !state.editable} />
                    <td>
                      <p className="font-medium text-foreground">{row.label}</p>
                      <p className="text-xs text-muted-foreground">{row.name}</p>
                    </td>
                    <td data-field="access">
                      <AccessLevelChoice
                        row={row}
                        value={row.level}
                        mode={state.mode}
                        disabled={!state.editable || saving}
                        onChange={(level) => void change(row, level)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <TablePager total={table.shown.length} paged={table.paged} />
    </div>
  );
}
