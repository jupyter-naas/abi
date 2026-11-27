'use client';

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { draftKey, isOffered, itemName, itemsWithOffered, offerChanges } from '@/components/access/offer/offer-model';
import '@/components/access/offer/offer.css';
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
import { reloadWorkspaceResources } from '@/hooks/use-workspace-resources';
import { PolicyPicker } from '@/components/settings/policy-picker';
import { BulkBar, SelectAllCell, SelectRowCell, useRowSelection, type BulkAction } from '@/components/settings/bulk-access';
import { isOrgTarget } from '@/lib/access-model/target';
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
  groupCellValues,
  groupSearchTexts,
  groupSummary,
  moduleDrafts,
  moduleExportRow,
  moduleGroups,
  offerSummary,
  type ModuleGroup,
  type ModuleRow,
} from './modules-model';

/** The batch actions on modules: each one offered whole, or all of it taken back. */
const BULK_ACTIONS: BulkAction[] = [
  {
    id: 'offer',
    label: 'Offer',
    question: (count, plural) => `Offer ${count} ${plural} whole?`,
    detail: (count) =>
      `Every kind of ${count === 1 ? 'it' : 'each'} is offered, what ${count === 1 ? 'it adds' : 'they add'} later too, in one save.`,
    confirm: 'Offer',
  },
  {
    id: 'take-back',
    label: 'Take back',
    question: (count, plural) => `Take back ${count} ${plural}?`,
    detail: () => 'Every kind and every item offered one by one is taken back, in one save.',
    confirm: 'Take back',
  },
];

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
 * is a module, switched whole (every kind of it, what it adds later too) or unfolded by its
 * contents: each kind (agents, apps, workflows, pipelines) switched whole, or unfolded again to
 * switch it item by item. Each switch is one write of "<W> access" as the caller;
 * IAM says what may change. The pages under Features then show what is offered.
 */
export function WorkspaceModules({
  workspaceId,
  api = DEFAULT_IAM_API,
  offerApi = DEFAULT_OFFER_API,
  initialPolicy = null,
  onPolicyChange,
  pickerPrefix,
  initialSearch = null,
}: {
  workspaceId: string;
  api?: IamAdminApi;
  offerApi?: OfferApi;
  /** The policy edited first (`?policy=`); "<W> access" when null. */
  initialPolicy?: string | null;
  /** Told when another policy is picked (null: "<W> access"). */
  onPolicyChange?: (policyId: string | null) => void;
  /** Before the Policy dropdown, in its row: Platform settings' Organization picker. */
  pickerPrefix?: ReactNode;
  /** The search the table opens with (`?module=`: a page under Features linking to a module's row). */
  initialSearch?: string | null;
}) {
  const [policyId, setPolicyId] = useState<string | null>(initialPolicy);
  const [offer, setOffer] = useState<OfferState | null>(null);
  const [publishers, setPublishers] = useState<PublishersView | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  // The modules unfolded by their contents, and the kinds unfolded item by item.
  const [openModules, setOpenModules] = useState<Record<string, boolean>>({});
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
    setOpenModules({});
    setOpen({});
    setItems({});
    setNotice('');
    void load();
  }, [load]);

  const rows = useMemo(() => (offer ? moduleGroups(publishers, offer.offered) : []), [offer, publishers]);
  const table = useSettingsTable({
    rows,
    columns: MODULE_COLUMNS,
    cellValues: groupCellValues,
    searchTexts: groupSearchTexts,
    initialSort: 'module',
  });
  // A link from Agents, Apps or Workflows opens on its module's row: the search set once.
  const searched = useRef(false);
  useEffect(() => {
    if (searched.current || !initialSearch) return;
    searched.current = true;
    table.setSearch(initialSearch);
  }, [initialSearch, table]);

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

  const toggle = (kind: OfferKind, module: string, name: string, label: string, on: boolean) =>
    saveDrafts({ [draftKey(kind, module, name)]: on }, label, on);

  /** One write of the policy for every switch a change makes (a whole module: each kind of it). */
  const saveDrafts = async (drafts: Record<string, boolean>, label: string, on: boolean) => {
    if (!offer) return;
    const changes = offerChanges(offer.offered, drafts);
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
      if (editsOffer(next) && !isOrgTarget(workspaceId)) void reloadWorkspaceResources(workspaceId);
    } catch (e) {
      setError(message(e, 'Could not save the offer.'));
    } finally {
      setSaving(false);
    }
  };

  // Modules checked for a batch change (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => table.shown.map((group) => group.key), [table.shown]));
  /** The selected modules a batch action fits: offering needs the right to give it here. */
  const bulkGroups = (id: string) =>
    rows.filter((group) => selection.selected.has(group.key) && (id === 'take-back' || group.grantable || group.offer === 'whole'));
  /** Offer every selected module whole, or take all of each back, in one write. */
  const applyBulk = async (id: string) => {
    const on = id === 'offer';
    const groups = bulkGroups(id);
    const drafts = Object.assign({}, ...groups.map((group) => moduleDrafts(group, on)));
    await saveDrafts(drafts, `${groups.length} module${groups.length === 1 ? '' : 's'}`, on);
  };

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    const kinds = table.shown.flatMap((group) => group.kinds);
    downloadTableExport(MODULE_EXPORT_HEADERS, kinds.map(moduleExportRow), format, `modules_${date}`, 'Modules');
  };

  const editable = offer?.editable ?? false;
  const moduleCount = rows.length;
  const onOffer = editsOffer(offer);
  const access = offer?.access_policy ?? null;
  const edited = offer?.policy ?? access;
  const editedHref = edited ? ownerHref(edited.owner_scope, edited.id) : null;
  const pick = (id: string) => {
    const next = access && id === access.id ? null : id;
    setPolicyId(next);
    onPolicyChange?.(next);
  };
  // The select column, then the table's own.
  const colSpan = MODULE_COLUMNS.length + 1;

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Modules"
        // One value: how many modules (one row each).
        badge={offer ? `${moduleCount} module${moduleCount === 1 ? '' : 's'}` : undefined}
        description={
          !onOffer && edited ? (
            <>
              What {editedHref ? <Link href={editedHref}>{edited.name}</Link> : edited.name} grants whoever holds it of
              each module, whole or item by item, within the workspace&apos;s offer{access ? ` (${access.name})` : ''}.
            </>
          ) : (
            isOrgTarget(workspaceId)
              ? 'What the workspaces of this organization may offer of each module: its agents, apps, workflows and pipelines, whole (what the module adds later too) or item by item. A workspace never offers what is not offered here.'
              : "What this workspace offers of each module: its agents, apps, workflows and pipelines, whole (what the module adds later too) or item by item. The pages under Features then show what is offered; each person's level decides what they do with it."
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
        <PolicyPicker policies={offer?.policies} current={edited} value={edited?.id} onChange={pick} disabled={saving} />
      </div>

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
            meta={<SettingsTableClear table={table} />}
          />
          <BulkBar
            selection={selection}
            noun="module"
            actions={BULK_ACTIONS}
            onApply={applyBulk}
            skippedFor={(id) => selection.selected.size - bulkGroups(id).length}
            disabled={!editable || saving}
          />
          <div className="org-settings-users-table-wrap">
            <table className="org-settings-users-table">
              <SettingsTableHead
                table={table}
                leading={
                  <SelectAllCell
                    selection={selection}
                    keys={table.shown.map((group) => group.key)}
                    noun="module"
                    disabled={!editable || saving}
                  />
                }
              />
              <tbody>
                {table.shown.length === 0 && <SettingsTableNoMatch colSpan={colSpan} noun="modules" />}
                {table.paged.pageRows.map((group) => (
                  <Fragment key={group.key}>
                    <ModuleLine
                      group={group}
                      select={
                        <SelectRowCell
                          selection={selection}
                          rowKey={group.key}
                          label={group.module}
                          disabled={!editable || saving}
                        />
                      }
                      unfolded={!!openModules[group.key]}
                      disabled={!editable || saving}
                      onUnfold={() => setOpenModules((current) => ({ ...current, [group.key]: !current[group.key] }))}
                      onSwitch={(on) => void saveDrafts(moduleDrafts(group, on), group.module, on)}
                    />
                    {openModules[group.key] &&
                      group.kinds.map((row) => {
                        const whole = row.offer === 'whole';
                        const shown = items[row.key];
                        const single = row.kindLabel.toLowerCase().replace(/s$/, '');
                        return (
                          <Fragment key={row.key}>
                            <tr data-module-kind={row.key} className="align-top access-offer-kind-row">
                              <td />
                              <td className="access-offer-indent-1">
                                <button
                                  type="button"
                                  className="access-offer-expand access-offer-expand-label text-muted-foreground"
                                  aria-expanded={!!open[row.key]}
                                  aria-label={`${open[row.key] ? 'Fold' : 'Unfold'} the ${row.kindLabel.toLowerCase()} of ${row.module}`}
                                  data-action="items"
                                  onClick={() => toggleOpen(row)}
                                >
                                  {open[row.key] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                  {row.kindLabel}
                                </button>
                              </td>
                              <td />
                              <td data-field="offer">
                                <div className="flex items-center gap-2">
                                  <OfferBox
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
                            </tr>
                            {open[row.key] &&
                              (!shown || shown.status === 'loading' ? (
                                <tr data-module-items={row.key}>
                                  <td colSpan={colSpan} className="access-offer-indent-2 access-policy-muted">
                                    Loading…
                                  </td>
                                </tr>
                              ) : shown.status === 'failed' ? (
                                <tr data-module-items={row.key}>
                                  <td colSpan={colSpan} className="access-offer-indent-2 access-policy-error">
                                    {shown.error}
                                  </td>
                                </tr>
                              ) : (
                                <>
                                  {/* One row per item: its name two steps in, its switch in Offered. */}
                                  {itemsWithOffered(shown.items, offer.offered[row.kind], row.module).map((item) => (
                                    <tr
                                      key={item.name}
                                      data-module-items={row.key}
                                      data-offer-item={`${row.module}/${item.name}`}
                                      className="align-top"
                                    >
                                      <td />
                                      <td className="access-offer-indent-2 text-sm text-foreground">{item.label}</td>
                                      <td />
                                      <td data-field="offer">
                                        <OfferBox
                                          label={`Offer ${item.label}`}
                                          on={isOffered(offer.offered, row.kind, row.module, item.name)}
                                          disabled={!editable || saving || whole}
                                          onChange={(next) => void toggle(row.kind, row.module, item.name, item.label, next)}
                                        />
                                      </td>
                                    </tr>
                                  ))}
                                  {!shown.listed && (
                                    <tr data-module-items={row.key}>
                                      <td colSpan={colSpan} className="access-offer-indent-2 access-policy-muted">
                                        Its items are not listed: offer them all.
                                      </td>
                                    </tr>
                                  )}
                                </>
                              ))}
                          </Fragment>
                        );
                      })}
                  </Fragment>
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

/** A module's row: its name, its contents, its switch (the whole module) and the unfold button. */
function ModuleLine({
  group,
  select,
  unfolded,
  disabled,
  onUnfold,
  onSwitch,
}: {
  group: ModuleGroup;
  /** Its checkbox, for a batch change. */
  select: ReactNode;
  unfolded: boolean;
  disabled: boolean;
  onUnfold: () => void;
  onSwitch: (on: boolean) => void;
}) {
  const whole = group.offer === 'whole';
  return (
    <tr data-module={group.key} className="align-top">
      {select}
      <td>
        <button
          type="button"
          className="access-offer-expand access-offer-expand-label font-medium text-foreground"
          aria-expanded={unfolded}
          aria-label={`${unfolded ? 'Fold' : 'Unfold'} the contents of ${group.module}`}
          data-action="contents"
          onClick={onUnfold}
        >
          {unfolded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {group.module}
        </button>
      </td>
      <td className="text-muted-foreground">{group.kinds.map((k) => k.kindLabel).join(', ')}</td>
      <td data-field="offer">
        <div className="flex items-center gap-2">
          <OfferBox
            label={`Offer all of ${group.module}`}
            on={whole}
            disabled={disabled || (!group.grantable && !whole)}
            onChange={onSwitch}
          />
          <span className="text-xs text-muted-foreground">{groupSummary(group)}</span>
        </div>
      </td>
    </tr>
  );
}

/** The on/off control of Settings, the square checkbox (Access › Modules' sliders are gone). */
function OfferBox({
  label,
  on,
  disabled,
  onChange,
}: {
  label: string;
  on: boolean;
  disabled?: boolean;
  onChange: (on: boolean) => void;
}) {
  return (
    <Checkbox
      aria-label={label}
      title={label}
      checked={on}
      disabled={disabled}
      data-offer-switch=""
      onCheckedChange={onChange}
    />
  );
}
