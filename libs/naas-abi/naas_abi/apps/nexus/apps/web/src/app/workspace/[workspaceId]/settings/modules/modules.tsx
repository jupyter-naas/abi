'use client';

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { OfferSwitch } from '@/components/access/offer/offer-editor';
import { draftKey, isOffered, itemName, itemsWithOffered, offerChanges } from '@/components/access/offer/offer-model';
import '@/components/access/offer/offer.css';
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
import { reloadWorkspaceResources } from '@/hooks/use-workspace-resources';
import { PolicyPicker } from '@/components/settings/policy-picker';
import { ownerHref } from '@/components/access/policies/policy-owners';
import Link from 'next/link';
import {
  OFFER_KINDS,
  WHOLE_MODULE,
  createOfferApi,
  type OfferApi,
  type OfferKind,
  type OfferState,
} from '@/lib/access-model/workspace-offer';
import { createIamAdminApi, type IamAdminApi } from '@/lib/iam-admin/api';
import type { PublishersView } from '@/lib/iam-admin/types';
import {
  MODULE_COLUMNS,
  MODULE_EXPORT_HEADERS,
  moduleCellValues,
  moduleExportRow,
  moduleRows,
  moduleSearchTexts,
  offerSummary,
  type ModuleRow,
} from './modules-model';

const DEFAULT_OFFER_API = createOfferApi();
const DEFAULT_IAM_API = createIamAdminApi();
const ITEM_LIMIT = 200;

type Items =
  | { status: 'loading' }
  | { status: 'ready'; listed: boolean; items: { name: string; label: string }[] }
  | { status: 'failed'; error: string };

const message = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

/** Whether the state read is "<W> access", the workspace's offer (not another policy of it). */
const editsOffer = (state: OfferState | null) =>
  !state?.policy || !state.access_policy || state.policy.id === state.access_policy.id;

/**
 * Settings › Access › Modules: what the workspace offers of each module, laid out as Users. A row
 * is a module's agents, apps, workflows or pipelines: offered whole (what the module adds later
 * too), item by item (unfold it), or not. Each switch is one write of "<W> access" as the caller;
 * IAM says what may change. The pages under Features then show what is offered.
 */
export function WorkspaceModules({
  workspaceId,
  api = DEFAULT_IAM_API,
  offerApi = DEFAULT_OFFER_API,
  initialPolicy = null,
  onPolicyChange,
}: {
  workspaceId: string;
  api?: IamAdminApi;
  offerApi?: OfferApi;
  /** The policy edited first (`?policy=`); "<W> access" when null. */
  initialPolicy?: string | null;
  /** Told when another policy is picked (null: "<W> access"). */
  onPolicyChange?: (policyId: string | null) => void;
}) {
  const [policyId, setPolicyId] = useState<string | null>(initialPolicy);
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [publishers, setPublishers] = useState<PublishersView | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [items, setItems] = useState<Record<string, Items>>({});

  const load = useCallback(async () => {
    try {
      const read = await offerApi.read(workspaceId, policyId);
      setOffer(read);
      setError('');
      setPublishers(await api.publishers(read.scope).catch(() => null));
    } catch (e) {
      setError(message(e, 'Could not read what this workspace offers.'));
    }
  }, [api, offerApi, workspaceId, policyId]);

  useEffect(() => {
    setOffer(null);
    setPublishers(null);
    setOpen({});
    setItems({});
    setNotice('');
    void load();
  }, [load]);

  const rows = useMemo(() => (offer ? moduleRows(publishers, offer.offered) : []), [offer, publishers]);
  const table = useSettingsTable({
    rows,
    columns: MODULE_COLUMNS,
    cellValues: moduleCellValues,
    searchTexts: moduleSearchTexts,
    initialSort: 'module',
  });

  const loadItems = async (row: ModuleRow) => {
    if (!offer) return;
    setItems((current) => ({ ...current, [row.key]: { status: 'loading' } }));
    const type = OFFER_KINDS.find((k) => k.kind === row.kind)!.type;
    try {
      const page = await api.resources({ scope: offer.scope, service: 'module', type, module: row.module, limit: ITEM_LIMIT });
      setItems((current) => ({
        ...current,
        [row.key]: {
          status: 'ready',
          listed: page.listed,
          items: page.items.map((item) => ({
            name: itemName(row.module, item.id),
            label: item.label || itemName(row.module, item.id),
          })),
        },
      }));
    } catch (e) {
      setItems((current) => ({ ...current, [row.key]: { status: 'failed', error: message(e, 'Could not list them.') } }));
    }
  };

  const toggleOpen = (row: ModuleRow) => {
    const next = !open[row.key];
    setOpen((current) => ({ ...current, [row.key]: next }));
    if (next && !items[row.key]) void loadItems(row);
  };

  const toggle = async (kind: OfferKind, module: string, name: string, label: string, on: boolean) => {
    if (!offer) return;
    const changes = offerChanges(offer.offered, { [draftKey(kind, module, name)]: on });
    if (changes.length === 0) return;
    setSaving(true);
    setNotice('');
    try {
      const next = await offerApi.save(workspaceId, changes, policyId);
      setOffer(next);
      setError('');
      const name = editsOffer(next) ? 'the offer' : (next.policy?.name ?? 'the policy');
      setNotice(`${label} ${on ? 'added to' : 'removed from'} ${name}.`);
      // The nav and the pages under Features follow what is offered.
      if (editsOffer(next)) void reloadWorkspaceResources(workspaceId);
    } catch (e) {
      setError(message(e, 'Could not save the offer.'));
    } finally {
      setSaving(false);
    }
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(MODULE_EXPORT_HEADERS, table.shown.map(moduleExportRow), format, `modules_${date}`, 'Modules');
  };

  const editable = offer?.editable ?? false;
  const offeredCount = rows.filter((row) => row.offer !== 'none').length;
  const onOffer = editsOffer(offer);
  const access = offer?.access_policy ?? null;
  const edited = offer?.policy ?? access;
  const editedHref = edited ? ownerHref(edited.owner_scope, edited.id) : null;
  const pick = (id: string) => {
    const next = access && id === access.id ? null : id;
    setPolicyId(next);
    onPolicyChange?.(next);
  };
  const colSpan = MODULE_COLUMNS.length + 1;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Modules"
        badge={
          offer
            ? onOffer
              ? `${offeredCount} offered · ${rows.length - offeredCount} not offered`
              : `${offeredCount} granted · ${rows.length - offeredCount} not granted`
            : undefined
        }
        description={
          !onOffer && edited ? (
            <>
              What {editedHref ? <Link href={editedHref}>{edited.name}</Link> : edited.name} grants whoever holds it of
              each module, whole or item by item, within the workspace&apos;s offer{access ? ` (${access.name})` : ''}.
            </>
          ) : (
            "What this workspace offers of each module: its agents, apps, workflows and pipelines, whole (what the module adds later too) or item by item. The pages under Features then show what is offered; each person's level decides what they do with it."
          )
        }
        actions={
          <>
            <PolicyPicker policies={offer?.policies} current={edited} value={edited?.id} onChange={pick} disabled={saving} />
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
          </>
        }
      />

      {error && (
        <SettingsNotice tone="error" icon={<AlertCircle size={14} />}>
          {error}
        </SettingsNotice>
      )}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-modules-notice="">
          {notice}
        </p>
      )}
      {offer && !editable && (
        <SettingsNotice tone="info">
          {edited
            ? `Read-only: IAM does not let you change ${edited.name}.`
            : 'This workspace has no access policy yet.'}
        </SettingsNotice>
      )}

      {!offer ? (
        !error && <SettingsLoading label="Loading modules…" />
      ) : rows.length === 0 ? (
        <SettingsEmpty title="No module you may offer here." />
      ) : (
        <div className="space-y-4">
          <SettingsTableToolbar
            search={table.search}
            onSearchChange={table.setSearch}
            searchPlaceholder="Search module, agents, apps, workflows, offered…"
            meta={
              <>
                {countLabel(table.shown.length, rows.length, 'row')}
                <SettingsTableClear table={table} />
              </>
            }
          />
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead table={table} trailing={<th aria-label="Items" />} />
              <tbody>
                {table.shown.length === 0 && <SettingsTableNoMatch colSpan={colSpan} noun="modules" />}
                {table.paged.pageRows.map((row) => {
                  const whole = row.offer === 'whole';
                  const shown = items[row.key];
                  const single = row.kindLabel.toLowerCase().replace(/s$/, '');
                  return (
                    <Fragment key={row.key}>
                      <tr data-module={row.key} className="align-top">
                        <td className="font-medium text-foreground">{row.module}</td>
                        <td className="text-muted-foreground">{row.kindLabel}</td>
                        <td data-field="offer">
                          <div className="flex items-center gap-2">
                            <OfferSwitch
                              label={`Offer every ${single} of ${row.module}`}
                              on={whole}
                              disabled={!editable || saving || (!row.grantable && !whole)}
                              onChange={(next) =>
                                void toggle(row.kind, row.module, WHOLE_MODULE, `Every ${single} of ${row.module}`, next)
                              }
                            />
                            <span className="text-xs text-muted-foreground">{offerSummary(row)}</span>
                          </div>
                        </td>
                        <td className="whitespace-nowrap text-right">
                          <button
                            type="button"
                            className="access-offer-expand"
                            aria-expanded={!!open[row.key]}
                            data-action="items"
                            onClick={() => toggleOpen(row)}
                          >
                            {open[row.key] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            {row.kindLabel}
                          </button>
                        </td>
                      </tr>
                      {open[row.key] && (
                        <tr data-module-items={row.key}>
                          <td colSpan={colSpan}>
                            <ul className="access-offer-items" aria-label={`${row.kindLabel} of ${row.module}`}>
                              {!shown || shown.status === 'loading' ? (
                                <li className="access-policy-muted">Loading…</li>
                              ) : shown.status === 'failed' ? (
                                <li className="access-policy-error">{shown.error}</li>
                              ) : (
                                <>
                                  {itemsWithOffered(shown.items, offer.offered[row.kind], row.module).map((item) => (
                                    <li
                                      key={item.name}
                                      className="access-offer-row"
                                      data-offer-item={`${row.module}/${item.name}`}
                                    >
                                      <OfferSwitch
                                        label={`Offer ${item.label}`}
                                        on={isOffered(offer.offered, row.kind, row.module, item.name)}
                                        disabled={!editable || saving || whole}
                                        onChange={(next) => void toggle(row.kind, row.module, item.name, item.label, next)}
                                      />
                                      <span className="access-offer-name">{item.label}</span>
                                    </li>
                                  ))}
                                  {!shown.listed && (
                                    <li className="access-policy-muted">Its items are not listed: offer the whole module.</li>
                                  )}
                                </>
                              )}
                            </ul>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <TablePager total={table.shown.length} paged={table.paged} />
    </div>
  );
}
