'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertCircle, ArrowLeft, ShieldCheck, ShieldOff } from 'lucide-react';
import { authFetch, useAuthStore } from '@/stores/auth';
import { useConfirm } from '@/components/ui/dialogs';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { cellText, NULL_LABEL, REDACTED_LABEL, type CellValue } from '../../../lib/table-cells';
import { platformTablePath } from '../../../lib/tables';
import { useTablesView } from '../../../lib/tables-view';
import '@/app/organizations/[orgId]/settings/users/users.css';
import { readApiError, safeDecode } from '../../../lib/page-helpers';

/** One row, as `GET /api/admin/tables/{name}/rows/{id}` returns it. */
interface PlatformTableRow {
  name: string;
  label: string;
  description: string;
  id: string;
  primary_key: string[];
  columns: string[];
  row: Record<string, CellValue>;
}

/** Grant or remove platform superadmin access from a users row. */
function SuperadminAction({
  row,
  onChange,
  onError,
}: {
  row: Record<string, CellValue>;
  onChange: (isSuperadmin: boolean) => void;
  onError: (message: string) => void;
}) {
  const authUserId = useAuthStore((s) => s.user?.id);
  const { confirm, dialog } = useConfirm();
  const [pending, setPending] = useState(false);
  const userId = String(row.id);
  const isSuperadmin = row.is_superadmin === true;
  const isSelf = userId === authUserId;

  const toggle = async () => {
    const who = String(row.name || row.email || userId);
    if (
      isSuperadmin &&
      !(await confirm({ title: `Remove superadmin access from ${who}?`, confirmLabel: 'Remove' }))
    ) {
      return;
    }
    onError('');
    setPending(true);
    try {
      const res = await authFetch(`/api/admin/users/${encodeURIComponent(userId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_superadmin: !isSuperadmin }),
      });
      if (!res.ok) throw new Error(await readApiError(res, 'Failed to update user'));
      const updated: { is_superadmin: boolean } = await res.json();
      onChange(updated.is_superadmin);
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Failed to update user');
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="org-settings-users-secondary-button"
        disabled={pending || (isSuperadmin && isSelf)}
        title={isSuperadmin && isSelf ? 'You cannot remove your own superadmin access' : undefined}
        onClick={() => void toggle()}
      >
        {isSuperadmin ? <ShieldOff size={16} /> : <ShieldCheck size={16} />}
        {isSuperadmin ? 'Remove superadmin' : 'Make superadmin'}
      </button>
      {dialog}
    </>
  );
}

/**
 * One row of a table, field by field. Rows are read-only, except users rows,
 * which can grant or remove platform superadmin access.
 */
export default function PlatformTableRowPage() {
  const params = useParams<{ table: string; rowId: string }>();
  const tableName = safeDecode(params?.table ?? '');
  const rowId = safeDecode(params?.rowId ?? '');
  const tablePath = platformTablePath(tableName);
  const [data, setData] = useState<PlatformTableRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError('');
    setActionError('');
    setData(null);
    (async () => {
      try {
        const res = await authFetch(
          `/api/admin/tables/${encodeURIComponent(tableName)}/rows/${encodeURIComponent(rowId)}`
        );
        if (cancelled) return;
        if (!res.ok) {
          setLoadError(await readApiError(res, `Failed to load this row (HTTP ${res.status}).`));
          return;
        }
        const loaded: PlatformTableRow = await res.json();
        setData(loaded);
        useTablesView.getState().rememberLabels([loaded]);
      } catch {
        if (!cancelled) setLoadError('Failed to load this row. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tableName, rowId]);

  // Reading the tables takes nexus:ReadSystem; changing the flag, nexus:ManageSystem,
  // which `is_superadmin` reports. The API checks it either way.
  const canManageSystem = useAuthStore((s) => !!s.user?.is_superadmin);

  const setSuperadminFlag = (isSuperadmin: boolean) =>
    setData((current) =>
      current ? { ...current, row: { ...current.row, is_superadmin: isSuperadmin } } : current
    );

  return (
    <div className="org-settings-users-page platform-table-page">
      <div className="org-settings-users-main">
        <Link href={tablePath} className="platform-row-back">
          <ArrowLeft size={14} />
          {data?.label ?? tableName}
        </Link>

        <OrgSettingsPageHeader
          title={rowId}
          badge={tableName}
          subtitle={data?.description ?? ''}
          actions={
            tableName === 'users' && data && canManageSystem ? (
              <SuperadminAction
                row={data.row}
                onChange={setSuperadminFlag}
                onError={setActionError}
              />
            ) : undefined
          }
        />

        {(loadError || actionError) && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError || actionError}</span>
          </div>
        )}

        <div className="org-settings-users-table-wrap">
          {loading ? (
            <div className="org-settings-loading">Loading row...</div>
          ) : !data ? null : (
            <table className="org-settings-users-table platform-row-table">
              <tbody>
                {data.columns.map((column) => {
                  const value = data.row[column];
                  const text = cellText(value);
                  const className =
                    text === NULL_LABEL && value === null
                      ? 'platform-table-cell-null'
                      : text === REDACTED_LABEL
                        ? 'platform-table-cell-redacted'
                        : undefined;
                  return (
                    <tr key={column}>
                      <th scope="row" className="platform-row-field">
                        {column}
                        {data.primary_key.includes(column) && (
                          <span className="platform-schema-tag">primary</span>
                        )}
                      </th>
                      <td className={className}>{text}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {tableName === 'users' && (
          <p className="org-settings-footnote">
            Superadmins reach Platform Settings, platform services and the live event stream.
            Accounts listed under <code>users:</code> in the config are promoted again on every
            boot.
          </p>
        )}
      </div>
    </div>
  );
}
