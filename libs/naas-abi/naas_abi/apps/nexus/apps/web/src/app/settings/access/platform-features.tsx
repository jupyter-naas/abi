'use client';

/**
 * Platform settings › Access › Features, the platform picked: "Platform access", what the platform
 * offers every organization. Every known feature is listed, offered or not; an organization's
 * Features lists those offered, and a feature not offered is usable nowhere. A table of switches,
 * as the other Access pages: each change is saved at once, and said; the features selected change
 * together, asked first.
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import { Notice } from '@/components/ui/notice';
import { BulkBar, SelectAllCell, SelectRowCell, onOffActions, useRowSelection } from '@/components/settings/bulk-access';
import { SettingsPageHeader, SettingsTableToolbar } from '@/components/settings/settings-ui';
import {
  SettingsTableClear,
  SettingsTableHead,
  SettingsTableNoMatch,
  useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { PLATFORM_TARGET } from '@/lib/access-model/target';
import {
  createFeatureAccessApi,
  type FeatureAccessApi,
} from '@/app/workspace/[workspaceId]/settings/features/feature-access-api';
import {
  featureDescription,
  type FeatureAccessState,
  type FeatureRow,
} from '@/app/workspace/[workspaceId]/settings/features/feature-access-model';
import '@/app/organizations/[orgId]/settings/users/users.css';

const DEFAULT_API = createFeatureAccessApi();

type ColumnId = 'feature' | 'description' | 'offered';
const COLUMNS: { id: ColumnId; label: string }[] = [
  { id: 'feature', label: 'Feature' },
  { id: 'description', label: 'Description' },
  { id: 'offered', label: 'Offered' },
];

const offeredLabel = (row: FeatureRow) => (row.choice === 'everyone' ? 'Offered' : 'Not offered');

const BULK_ACTIONS = onOffActions({ on: 'Offer', off: 'Take back' }, (on) =>
  on
    ? 'Every organization may offer them to its workspaces, in one save.'
    : 'No organization offers them any more, and nobody uses them, in one save.'
);

function message(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function PlatformFeatures({ api = DEFAULT_API, pickerPrefix }: { api?: FeatureAccessApi; pickerPrefix?: ReactNode }) {
  const [state, setState] = useState<FeatureAccessState | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.read(PLATFORM_TARGET));
      setError('');
    } catch (e) {
      setError(message(e, 'Could not read what the platform offers.'));
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = useMemo(() => state?.features ?? [], [state]);
  const table = useSettingsTable({
    rows,
    columns: COLUMNS,
    cellValues: (row: FeatureRow, column: ColumnId) =>
      column === 'feature' ? [row.label] : column === 'description' ? [featureDescription(row.key)] : [offeredLabel(row)],
    searchTexts: (row: FeatureRow) => [row.label, row.key, featureDescription(row.key), offeredLabel(row)],
    initialSort: 'feature',
  });
  const selection = useRowSelection(useMemo(() => table.shown.map((row) => row.key), [table.shown]));

  /** One write of "Platform access" for `on`/`off` of `keys`, then what it did said. */
  const save = async (keys: string[], on: boolean) => {
    const changes = keys
      .map((key) => rows.find((row) => row.key === key))
      .filter((row): row is FeatureRow => !!row && row.editable && (row.choice === 'everyone') !== on)
      .map((row) => ({ feature: row.key, choice: on ? ('everyone' as const) : ('nobody' as const), principals: [] }));
    if (changes.length === 0) return;
    setSaving(true);
    setNotice('');
    try {
      const next = await api.save(PLATFORM_TARGET, changes);
      setState(next);
      const refused = Object.values(next.errors ?? {});
      if (refused.length > 0) setError(refused.join(' '));
      else {
        setError('');
        setNotice(`${changes.length} feature${changes.length === 1 ? '' : 's'} ${on ? 'offered' : 'taken back'}.`);
      }
    } catch (e) {
      setError(message(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  };

  const offeredCount = rows.filter((row) => row.choice === 'everyone').length;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Features"
        badge={state ? `${rows.length} features` : undefined}
        description="What the platform offers every organization: an organization offers its workspaces only these"
      />
      {pickerPrefix ? <div className="-mt-3 flex flex-wrap items-center gap-4">{pickerPrefix}</div> : null}
      {error && (
        <Notice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </Notice>
      )}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-platform-features-notice="">
          {notice}
        </p>
      )}
      {!state ? (
        !error && <Loading label="Loading features…" />
      ) : rows.length === 0 ? (
        <EmptyState framed title="No feature." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search feature, offered, not offered…"
            meta={<SettingsTableClear table={table} />}
          />
          <BulkBar
            selection={selection}
            noun="feature"
            actions={BULK_ACTIONS}
            onApply={(id) => save([...selection.selected], id === 'on')}
            skippedFor={() => rows.filter((row) => selection.selected.has(row.key) && !row.editable).length}
            change="this change"
            disabled={saving}
          />
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table" data-platform-features="" data-offered-count={offeredCount}>
              <SettingsTableHead
                table={table}
                leading={
                  <SelectAllCell
                    selection={selection}
                    keys={table.shown.filter((row) => row.editable).map((row) => row.key)}
                    noun="feature"
                    disabled={saving}
                  />
                }
              />
              <tbody>
                {table.shown.length === 0 && <SettingsTableNoMatch colSpan={COLUMNS.length + 1} noun="features" />}
                {table.paged.pageRows.map((row) => (
                  <tr key={row.key} data-feature={row.key} className="align-top">
                    <SelectRowCell selection={selection} rowKey={row.key} label={row.label} disabled={saving || !row.editable} />
                    <td className="font-medium text-foreground">{row.label}</td>
                    <td className="text-sm text-muted-foreground">{featureDescription(row.key)}</td>
                    <td>
                      <span className="inline-flex items-center gap-2">
                        <Checkbox
                          checked={row.choice === 'everyone'}
                          disabled={!row.editable || saving}
                          aria-label={`Offer ${row.label}`}
                          data-offered={row.key}
                          onCheckedChange={(checked) => void save([row.key], checked)}
                        />
                        <span className="text-xs text-muted-foreground">{offeredLabel(row)}</span>
                      </span>
                      {!row.editable && row.reason ? <p className="workspace-features-note">{row.reason}</p> : null}
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
