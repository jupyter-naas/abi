'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { CompanyConfig, SectionProps } from '@/lib/types';
import { isAdminRole } from '@/lib/types';
import { isConsolidation } from '@/lib/config/entityHelpers';
import { formatEntityName } from '@/lib/format';
import {
  aggregateRecoveryActionKpis,
  DEFAULT_INVOICE_TABLE_COLUMN_FILTERS,
  filterUnpaidInvoiceRecords,
  isUnpaidClientsDataset,
  recoveryActionForRecord,
  recoveryKpiTableView,
  recoveryRuleHint,
  recoveryRulesHint,
  recoveryToneForLabel,
  resolveRecoveryCharts,
  type RecoveryKpiFilterPreset,
  type RecoveryTone,
  type UnpaidClientsDataset,
} from '@/lib/data/unpaidClients';
import { PageTitle } from '@/components/layout/PageTitle';
import { InvoiceActionsCell } from '@/components/dashboard/InvoiceActionsCell';
import { InvoiceAnnotationCell } from '@/components/dashboard/InvoiceAnnotationCell';
import { HorizontalBarChart } from '@/components/dashboard/HorizontalBarChart';
import { KpiCard } from '@/components/dashboard/KpiCard';
import { DataTable } from '@/components/dashboard/DataTable';
import type { DataTableColumn } from '@/components/dashboard/DataTable';
import { Button } from '@/components/ui/Button';

const RECOVERY_TONE_TEXT_CLASS: Record<RecoveryTone, string> = {
  success: 'text-[var(--recovery-success)]',
  warning: 'text-[var(--recovery-warning)]',
  orange: 'text-[var(--recovery-orange)]',
  danger: 'text-[var(--recovery-danger)]',
};

function renderRecoveryLabel(value: unknown) {
  const label = String(value);
  const tone = recoveryToneForLabel(label);
  return (
    <span
      className={`block truncate ${tone ? `font-medium ${RECOVERY_TONE_TEXT_CLASS[tone]}` : ''}`}
    >
      {label}
    </span>
  );
}

const DETAIL_TABLE_COLUMNS: DataTableColumn[] = [
  { key: 'company', label: 'Company' },
  { key: 'site', label: 'Project' },
  { key: 'client', label: 'Customer' },
  { key: 'categorie_2', label: 'Analytical category' },
  { key: 'invoice_ref', label: 'Invoice no.' },
  { key: 'due_date', label: 'Due date' },
  {
    key: 'recovery_action_label',
    label: 'Collection status',
    renderValue: renderRecoveryLabel,
  },
  {
    key: 'remaining_amount_ttc',
    label: 'Outstanding incl. tax',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
  {
    key: 'amount_ttc',
    label: 'Amount incl. tax',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
  {
    key: 'days_overdue',
    label: 'Days overdue',
    align: 'right' as const,
    valueStyle: 'decimal' as const,
    maximumFractionDigits: 0,
  },
];

type InvoiceAnnotationValues = {
  date_relance: string;
  notes: string;
};

type InvoiceAnnotationLogEntry = {
  event_id: string;
  company: string;
  organization_slug: string;
  site: string;
  client: string;
  categorie_2: string;
  invoice_number: string;
  status_relance: string;
  field: keyof InvoiceAnnotationValues;
  value: string;
  user: string;
  date_edited: string;
};

type InvoiceLogJoinInfo = {
  client: string;
  company: string;
  organizationSlug: string;
  site: string;
  categorie2: string;
};

const EMPTY_ANNOTATION: InvoiceAnnotationValues = { date_relance: '', notes: '' };

const ANNOTATION_FIELD_LABELS: Record<keyof InvoiceAnnotationValues, string> = {
  date_relance: 'Reminder date',
  notes: 'Notes',
};

function parseAnnotationLogEntry(
  record: Record<string, unknown>,
): InvoiceAnnotationLogEntry | null {
  if (typeof record.invoice_number !== 'string' || !record.invoice_number) {
    return null;
  }
  if (record.field !== 'date_relance' && record.field !== 'notes') {
    return null;
  }
  return {
    event_id: typeof record.event_id === 'string' ? record.event_id : '',
    company: typeof record.company === 'string' ? record.company : '',
    organization_slug:
      typeof record.organization_slug === 'string' ? record.organization_slug : '',
    site: typeof record.site === 'string' ? record.site : '',
    client: typeof record.client === 'string' ? record.client : '',
    categorie_2: typeof record.categorie_2 === 'string' ? record.categorie_2 : '',
    invoice_number: record.invoice_number,
    status_relance:
      typeof record.status_relance === 'string' ? record.status_relance : '',
    field: record.field,
    value: typeof record.value === 'string' ? record.value : '',
    user: typeof record.user === 'string' ? record.user : '',
    date_edited: typeof record.date_edited === 'string' ? record.date_edited : '',
  };
}

/** Local-time `YYYY-MM-DD HH:mm:ss` — readable and still sorts chronologically. */
function formatLogTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function annotationKey(invoiceNumber: string, statusRelance: string): string {
  return `${invoiceNumber}::${statusRelance}`;
}

type AnnotationTarget = {
  invoiceNumber: string;
  statusRelance: string;
  company: string;
  organizationSlug: string;
  site: string;
  client: string;
  categorie2: string;
};

function annotationTarget(row: Record<string, unknown>): AnnotationTarget {
  return {
    invoiceNumber: typeof row.invoice_ref === 'string' ? row.invoice_ref : '',
    statusRelance:
      typeof row.recovery_action_label === 'string' ? row.recovery_action_label : '',
    company: typeof row.company === 'string' ? row.company : '',
    organizationSlug: String(row.organization_slug ?? row.entity_id ?? ''),
    site: typeof row.site === 'string' ? row.site : '',
    client: typeof row.client === 'string' ? row.client : '',
    categorie2: typeof row.categorie_2 === 'string' ? row.categorie_2 : '',
  };
}

function buildDetailTableColumns(
  entitySlug: string,
  showCompanyColumn: boolean,
  updateAnnotation: (
    target: AnnotationTarget,
    patch: Partial<InvoiceAnnotationValues>,
  ) => void,
): DataTableColumn[] {
  const columns = (
    showCompanyColumn
      ? DETAIL_TABLE_COLUMNS
      : DETAIL_TABLE_COLUMNS.filter((column) => column.key !== 'company')
  ).flatMap((column) =>
    column.key === 'recovery_action_label'
      ? [
          column,
          {
            key: 'date_relance',
            label: 'Reminder date',
            renderCell: (row: Record<string, unknown>) => {
              const target = annotationTarget(row);
              return (
                <InvoiceAnnotationCell
                  type="date"
                  value={typeof row.date_relance === 'string' ? row.date_relance : ''}
                  ariaLabel={`Reminder date — invoice ${target.invoiceNumber}`}
                  onSave={(value) =>
                    updateAnnotation(target, { date_relance: value })
                  }
                />
              );
            },
          } satisfies DataTableColumn,
        ]
      : [column],
  );

  return [
    ...columns,
    {
      key: 'notes',
      label: 'Notes',
      cellClassName: '!whitespace-normal align-top',
      renderCell: (row) => {
        const target = annotationTarget(row);
        return (
          <InvoiceAnnotationCell
            type="textarea"
            value={typeof row.notes === 'string' ? row.notes : ''}
            ariaLabel={`Notes — invoice ${target.invoiceNumber}`}
            placeholder="Add a note"
            onSave={(value) => updateAnnotation(target, { notes: value })}
          />
        );
      },
    },
    {
      key: '_actions',
      label: 'Actions',
      renderCell: (row) => (
        <InvoiceActionsCell
          entitySlug={entitySlug}
          invoiceId={String(row.invoice_id ?? '')}
          organizationSlug={String(row.organization_slug ?? row.entity_id ?? '')}
          invoiceRef={typeof row.invoice_ref === 'string' ? row.invoice_ref : null}
          pennylaneTransactionsUrl={
            typeof row.pennylane_transactions_url === 'string'
              ? row.pennylane_transactions_url
              : null
          }
          pennylaneCompanyId={
            typeof row.pennylane_company_id === 'number'
              ? row.pennylane_company_id
              : null
          }
        />
      ),
    },
  ];
}

export function InvoicesSection({ user, entity, site, company, datasets }: SectionProps) {
  const detailTableRef = useRef<HTMLDivElement>(null);
  const [detailFilters, setDetailFilters] = useState<Record<string, string>>(
    DEFAULT_INVOICE_TABLE_COLUMN_FILTERS,
  );
  const [detailShowAllRows, setDetailShowAllRows] = useState(false);
  const [annotations, setAnnotations] = useState<
    Record<string, InvoiceAnnotationValues>
  >({});
  const [annotationHistory, setAnnotationHistory] = useState<
    InvoiceAnnotationLogEntry[]
  >([]);

  const refreshAnnotations = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/entities/${entity.url_slug}/invoices/annotations`,
      );
      if (!response.ok) {
        return;
      }
      const payload = (await response.json()) as {
        records?: Array<Record<string, unknown>>;
        history?: Array<Record<string, unknown>>;
      };
      const map: Record<string, InvoiceAnnotationValues> = {};
      for (const record of payload.records ?? []) {
        if (typeof record.invoice_number !== 'string') {
          continue;
        }
        const statusRelance =
          typeof record.status_relance === 'string' ? record.status_relance : '';
        map[annotationKey(record.invoice_number, statusRelance)] = {
          date_relance:
            typeof record.date_relance === 'string' ? record.date_relance : '',
          notes: typeof record.notes === 'string' ? record.notes : '',
        };
      }
      setAnnotations(map);
      setAnnotationHistory(
        (payload.history ?? [])
          .map(parseAnnotationLogEntry)
          .filter((entry): entry is InvoiceAnnotationLogEntry => entry !== null),
      );
    } catch {
      // Leave current state untouched when the fetch fails; cells stay editable.
    }
  }, [entity.url_slug]);

  useEffect(() => {
    void refreshAnnotations();
  }, [refreshAnnotations]);

  const updateAnnotation = useCallback(
    (target: AnnotationTarget, patch: Partial<InvoiceAnnotationValues>) => {
      if (!target.invoiceNumber) {
        return;
      }
      const key = annotationKey(target.invoiceNumber, target.statusRelance);
      const nextValues = { ...(annotations[key] ?? EMPTY_ANNOTATION), ...patch };
      setAnnotations((current) => ({ ...current, [key]: nextValues }));
      void fetch(`/api/entities/${entity.url_slug}/invoices/annotations`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          invoice_number: target.invoiceNumber,
          status_relance: target.statusRelance,
          company: target.company || (company?.display_name ?? ''),
          organization_slug:
            target.organizationSlug || (company?.organization_slug ?? ''),
          site: target.site,
          client: target.client,
          categorie_2: target.categorie2,
          ...nextValues,
        }),
      })
        .then(async (response) => {
          if (!response.ok) {
            return;
          }
          const payload = (await response.json()) as {
            log_entries?: Array<Record<string, unknown>>;
          };
          const entries = (payload.log_entries ?? [])
            .map(parseAnnotationLogEntry)
            .filter((entry): entry is InvoiceAnnotationLogEntry => entry !== null);
          if (entries.length > 0) {
            setAnnotationHistory((current) => [...current, ...entries]);
          }
        })
        .catch(() => {
          // Keep the optimistic value; it will re-sync on next load.
        });
    },
    [annotations, company, entity.url_slug],
  );

  const unpaidDataset = datasets.unpaid_clients;
  const data: UnpaidClientsDataset | null = isUnpaidClientsDataset(unpaidDataset)
    ? unpaidDataset
    : null;

  const summary = data?.summary;
  const tableInvoices = useMemo(() => data?.records ?? [], [data]);
  const unpaidInvoices = useMemo(
    () => filterUnpaidInvoiceRecords(tableInvoices),
    [tableInvoices],
  );
  const recoveryKpis = aggregateRecoveryActionKpis(unpaidInvoices);
  const { mise_en_demeure_by_client, arbitrage_by_client } = data
    ? resolveRecoveryCharts(data, unpaidInvoices)
    : { mise_en_demeure_by_client: [], arbitrage_by_client: [] };
  const dataAsOf = unpaidDataset?.data_version;

  const detailRecords = useMemo(
    () =>
      tableInvoices.map((row) => {
        const label = recoveryActionForRecord(row) || '—';
        const invoiceRef = typeof row.invoice_ref === 'string' ? row.invoice_ref : '';
        const annotation =
          annotations[annotationKey(invoiceRef, label)] ?? EMPTY_ANNOTATION;
        return {
          ...row,
          recovery_action_label: label,
          date_relance: annotation.date_relance,
          notes: annotation.notes,
        };
      }),
    [tableInvoices, annotations],
  );

  const invoiceLogJoinInfo = useMemo(() => {
    const map = new Map<string, InvoiceLogJoinInfo>();
    for (const row of tableInvoices) {
      if (typeof row.invoice_ref !== 'string' || !row.invoice_ref) {
        continue;
      }
      map.set(row.invoice_ref, {
        client: typeof row.client === 'string' ? row.client : '',
        company: typeof row.company === 'string' ? row.company : '',
        organizationSlug: String(row.organization_slug ?? row.entity_id ?? ''),
        site: typeof row.site === 'string' ? row.site : '',
        categorie2: typeof row.categorie_2 === 'string' ? row.categorie_2 : '',
      });
    }
    return map;
  }, [tableInvoices]);

  const openDetailTable = useCallback((preset: RecoveryKpiFilterPreset) => {
    const view = recoveryKpiTableView(preset);
    setDetailFilters(view.columnFilters);
    setDetailShowAllRows(view.showAllRows);
    window.requestAnimationFrame(() => {
      detailTableRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, []);

  const showCompanyColumn = isConsolidation(entity) && company === null;

  const detailTableColumns = useMemo(
    () => buildDetailTableColumns(entity.url_slug, showCompanyColumn, updateAnnotation),
    [entity.url_slug, showCompanyColumn, updateAnnotation],
  );

  const pageHint = `Follow-up of issued invoices still unpaid: ageing, amounts and collection status — ${formatEntityName(entity.display_name)}`;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={pageHint}>
          Customer Receivables
          {company
            ? ` — ${formatEntityName(company.display_name)}`
            : site
              ? ` — ${formatEntityName(site.name)}`
              : ''}
        </PageTitle>
      </div>

      {summary || recoveryKpis.en_cours.count > 0 ? (
        <div className="mb-8 flex flex-col gap-4">
          {summary ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <KpiCard
                label="Invoiced"
                value={summary.invoiced_amount_ttc}
                valueStyle="currency"
                subtitle={
                  summary.invoice_count
                    ? `${summary.invoice_count} invoice(s) · amount incl. tax`
                    : 'Amount incl. tax'
                }
                hint="Total invoiced incl. tax on the perimeter (all allowed invoices)."
              />
              <KpiCard
                label="Outstanding receivables"
                value={recoveryKpis.en_cours.amount}
                valueStyle="currency"
                hint={recoveryRulesHint()}
                subtitle={`${recoveryKpis.en_cours.count} invoice(s)`}
                onAction={
                  recoveryKpis.en_cours.count > 0
                    ? () => openDetailTable('all')
                    : undefined
                }
                actionLabel="View all unpaid invoices"
              />
              <KpiCard
                label="Collection rate"
                value={summary.recovery_rate}
                valueStyle="percent"
                percentInput="rate"
                maximumFractionDigits={1}
                tone="success"
                hint="(Invoiced incl. tax − outstanding incl. tax) / invoiced incl. tax on the filtered perimeter."
              />
            </div>
          ) : null}
          {recoveryKpis.en_cours.count > 0 ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <KpiCard
                label="Phone reminder"
                value={recoveryKpis.relance_telephonique.amount}
                valueStyle="currency"
                tone="warning"
                hint={recoveryRuleHint('Phone reminder')}
                subtitle={`${recoveryKpis.relance_telephonique.count} invoice(s)`}
                onAction={() => openDetailTable('relance_telephonique')}
                actionLabel="Filter on Phone reminder"
              />
              <KpiCard
                label="Formal notice"
                value={recoveryKpis.mise_en_demeure.amount}
                valueStyle="currency"
                tone="orange"
                hint={recoveryRuleHint('Formal notice')}
                subtitle={`${recoveryKpis.mise_en_demeure.count} invoice(s)`}
                onAction={() => openDetailTable('mise_en_demeure')}
                actionLabel="Filter on Formal notice"
              />
              <KpiCard
                label="Arbitration"
                value={recoveryKpis.arbitrage.amount}
                valueStyle="currency"
                tone="danger"
                hint={recoveryRuleHint('Arbitration')}
                subtitle={`${recoveryKpis.arbitrage.count} invoice(s)`}
                onAction={() => openDetailTable('arbitrage')}
                actionLabel="Filter on Arbitration"
              />
            </div>
          ) : null}
        </div>
      ) : summary ? (
        <div className="glass rounded-lg p-6 mb-8">
          <p className="text-sm text-[var(--text-muted)]">
            No outstanding receivable{dataAsOf ? ` as of ${dataAsOf}` : ''}.
          </p>
        </div>
      ) : null}

      {recoveryKpis.mise_en_demeure.count > 0 || recoveryKpis.arbitrage.count > 0 ? (
        <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <HorizontalBarChart
            title="Formal notice by customer"
            items={mise_en_demeure_by_client}
            emptyMessage="No receivable under formal notice by customer."
          />
          <HorizontalBarChart
            title="Arbitration by customer"
            items={arbitrage_by_client}
            emptyMessage="No receivable under arbitration by customer."
          />
        </div>
      ) : null}

      {tableInvoices.length > 0 ? (
        <div ref={detailTableRef} className="mb-8 scroll-mt-6">
          <PageTitle className="mb-6">Invoice detail</PageTitle>
          <DataTable
            records={detailRecords}
            columns={detailTableColumns}
            columnFilters={detailFilters}
            onColumnFiltersChange={setDetailFilters}
            showAllRows={detailShowAllRows}
            onShowAllRowsChange={setDetailShowAllRows}
            exportFileName="customer-receivables"
            emptyMessage="No invoice for this perimeter."
          />
        </div>
      ) : (
        <div ref={detailTableRef} className="mb-8 scroll-mt-6">
          <PageTitle className="mb-6">Invoice detail</PageTitle>
          <p className="text-sm text-[var(--text-muted)]">
            No invoice for this perimeter at the extraction date.
          </p>
        </div>
      )}

      <RelanceLogSection
        entitySlug={entity.url_slug}
        entries={annotationHistory}
        joinInfo={invoiceLogJoinInfo}
        companyFilter={company}
        showCompanyColumn={showCompanyColumn}
        isAdmin={isAdminRole(user.role)}
        onMutated={refreshAnnotations}
      />
    </div>
  );
}

type RelanceLogSectionProps = {
  entitySlug: string;
  entries: InvoiceAnnotationLogEntry[];
  joinInfo: Map<string, InvoiceLogJoinInfo>;
  companyFilter: CompanyConfig | null;
  /** Same visibility rule as the detail table's Company column. */
  showCompanyColumn: boolean;
  isAdmin: boolean;
  onMutated: () => void;
};

const logCheckboxClass = 'h-4 w-4 rounded border-[var(--border)] accent-[var(--secondary)]';

function RelanceLogSection({
  entitySlug,
  entries,
  joinInfo,
  companyFilter,
  showCompanyColumn,
  isAdmin,
  onMutated,
}: RelanceLogSectionProps) {
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmCount, setConfirmCount] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [restoreOpen, setRestoreOpen] = useState(false);
  const [restoreFrom, setRestoreFrom] = useState('');
  const [restoring, setRestoring] = useState(false);

  const visibleEntries = useMemo(() => {
    return [...entries]
      .sort((a, b) => (a.date_edited < b.date_edited ? 1 : -1))
      .map((entry) => {
        const joined = joinInfo.get(entry.invoice_number);
        return {
          ...entry,
          company: entry.company || joined?.company || '',
          organization_slug: entry.organization_slug || joined?.organizationSlug || '',
          site: entry.site || joined?.site || '',
          client: entry.client || joined?.client || '',
          categorie_2: entry.categorie_2 || joined?.categorie2 || '',
        };
      })
      .filter(
        (entry) =>
          !companyFilter ||
          entry.organization_slug === companyFilter.organization_slug,
      );
  }, [entries, joinInfo, companyFilter]);

  const selectableIds = useMemo(
    () => visibleEntries.map((entry) => entry.event_id).filter((id) => id),
    [visibleEntries],
  );

  // Drop selections that are no longer visible (deleted, or filtered out).
  useEffect(() => {
    setSelectedIds((current) => {
      const next = new Set([...current].filter((id) => selectableIds.includes(id)));
      return next.size === current.size ? current : next;
    });
  }, [selectableIds]);

  const allSelected =
    selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));

  const toggleAll = useCallback(() => {
    setSelectedIds((current) =>
      selectableIds.every((id) => current.has(id))
        ? new Set()
        : new Set(selectableIds),
    );
  }, [selectableIds]);

  const toggleOne = useCallback((eventId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(eventId)) {
        next.delete(eventId);
      } else {
        next.add(eventId);
      }
      return next;
    });
  }, []);

  const editValue = useCallback(
    (eventId: string, value: string) => {
      void fetch(`/api/entities/${entitySlug}/invoices/annotations`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_id: eventId, value }),
      })
        .then((response) => {
          if (response.ok) {
            onMutated();
          }
        })
        .catch(() => {});
    },
    [entitySlug, onMutated],
  );

  const restoreHistory = useCallback(async () => {
    setRestoring(true);
    try {
      const from = restoreFrom ? new Date(restoreFrom).toISOString() : undefined;
      const response = await fetch(
        `/api/entities/${entitySlug}/invoices/annotations/restore`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(from ? { from } : {}),
        },
      );
      if (response.ok) {
        setRestoreOpen(false);
        setRestoreFrom('');
        onMutated();
      }
    } catch {
      // Leave the restore panel open so the user can retry.
    } finally {
      setRestoring(false);
    }
  }, [entitySlug, onMutated, restoreFrom]);

  const confirmDelete = useCallback(async () => {
    setDeleting(true);
    try {
      const response = await fetch(
        `/api/entities/${entitySlug}/invoices/annotations`,
        {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ event_ids: [...selectedIds] }),
        },
      );
      if (response.ok) {
        setSelectedIds(new Set());
        setConfirmOpen(false);
        setConfirmCount('');
        onMutated();
      }
    } catch {
      // Leave the confirmation panel open so the user can retry.
    } finally {
      setDeleting(false);
    }
  }, [entitySlug, onMutated, selectedIds]);

  const columns = useMemo<DataTableColumn[]>(
    () => [
      {
        key: '_select',
        label: 'Sel.',
        renderHeader: () => (
          <input
            type="checkbox"
            className={logCheckboxClass}
            checked={allSelected}
            disabled={selectableIds.length === 0}
            aria-label="Select all"
            onChange={toggleAll}
          />
        ),
        renderCell: (row) => {
          const eventId = String(row.event_id ?? '');
          return (
            <input
              type="checkbox"
              className={logCheckboxClass}
              checked={eventId ? selectedIds.has(eventId) : false}
              disabled={!eventId}
              aria-label={`Select the row ${String(row.invoice_number ?? '')}`}
              onChange={() => toggleOne(eventId)}
            />
          );
        },
      },
      { key: 'date_edited', label: 'Edited on' },
      { key: 'user', label: 'User' },
      ...(showCompanyColumn ? [{ key: 'company', label: 'Company' }] : []),
      { key: 'site', label: 'Project' },
      { key: 'client', label: 'Customer' },
      { key: 'categorie_2', label: 'Analytical category' },
      { key: 'invoice_number', label: 'Invoice no.' },
      {
        key: 'status_relance',
        label: 'Collection status',
        renderValue: renderRecoveryLabel,
      },
      { key: 'field', label: 'Field' },
      {
        key: 'value',
        label: 'Value',
        cellClassName: '!whitespace-normal align-top',
        renderCell: (row) => {
          const eventId = String(row.event_id ?? '');
          const value = String(row.value ?? '');
          const fieldKey = String(row.field_key ?? '');
          if (!eventId || !isAdmin) {
            return (
              <span
                className={
                  fieldKey === 'notes'
                    ? 'block whitespace-pre-wrap'
                    : 'block truncate'
                }
              >
                {value}
              </span>
            );
          }
          return (
            <InvoiceAnnotationCell
              type={
                fieldKey === 'date_relance'
                  ? 'date'
                  : fieldKey === 'notes'
                    ? 'textarea'
                    : 'text'
              }
              value={value}
              ariaLabel={`Value — invoice ${String(row.invoice_number ?? '')}`}
              onSave={(next) => editValue(eventId, next)}
            />
          );
        },
      },
    ],
    [
      allSelected,
      editValue,
      isAdmin,
      selectableIds,
      selectedIds,
      showCompanyColumn,
      toggleAll,
      toggleOne,
    ],
  );

  const records = useMemo(
    () =>
      visibleEntries.map((entry) => ({
        event_id: entry.event_id,
        field_key: entry.field,
        date_edited: formatLogTimestamp(entry.date_edited),
        user: entry.user,
        company: entry.company,
        site: entry.site,
        client: entry.client,
        categorie_2: entry.categorie_2,
        invoice_number: entry.invoice_number,
        status_relance: entry.status_relance,
        field: ANNOTATION_FIELD_LABELS[entry.field],
        value: entry.value,
      })),
    [visibleEntries],
  );

  const restoreButton = isAdmin ? (
    <Button
      variant="ghost"
      isDisabled={restoring}
      onPress={() => setRestoreOpen(true)}
    >
      Restore the history
    </Button>
  ) : null;

  const restorePanel =
    isAdmin && restoreOpen ? (
      <div className="mb-4 flex flex-col gap-3 border border-[var(--border)] bg-[var(--accent)] p-4 text-sm">
        <p className="text-[var(--text)]">
          Restores the backed-up events (backup folder) into the log. Events
          already present are kept and the backup is left untouched. Leave the
          date empty to restore the whole history.
        </p>
        <label className="flex flex-wrap items-center gap-2 text-[var(--text)]">
          From (optional):
          <input
            type="datetime-local"
            value={restoreFrom}
            onChange={(event) => setRestoreFrom(event.target.value)}
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)] focus:border-[var(--secondary)] focus:outline-none"
            aria-label="Restore from this date"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button isDisabled={restoring} onPress={() => void restoreHistory()}>
            {restoring ? 'Restoring…' : 'Restore'}
          </Button>
          <Button
            variant="ghost"
            isDisabled={restoring}
            onPress={() => setRestoreOpen(false)}
          >
            Cancel
          </Button>
        </div>
      </div>
    ) : null;

  return (
    <div className="mb-8">
      <PageTitle
        className="mb-6"
        hint="History of the entries (reminder date and notes) made in the invoice detail. Each value stays editable row by row; the selection allows a bulk delete."
      >
        Collection follow-up
      </PageTitle>
      {records.length > 0 ? (
        <>
          {restorePanel}
          {confirmOpen && selectedIds.size > 0 ? (
            <div className="mb-4 flex flex-col gap-3 border border-[var(--recovery-danger)] bg-[color-mix(in_srgb,var(--recovery-danger)_8%,var(--surface))] p-4 text-sm">
              <p className="font-medium text-[var(--recovery-danger)]">
                ⚠️ You are about to permanently delete {selectedIds.size} log
                row(s). The values shown in the invoice detail will be recomputed
                without these events. This action cannot be undone.
              </p>
              <label className="flex flex-wrap items-center gap-2 text-[var(--text)]">
                Type the number of rows to delete to confirm:
                <input
                  type="number"
                  min={0}
                  value={confirmCount}
                  onChange={(event) => setConfirmCount(event.target.value)}
                  className="w-24 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)] focus:border-[var(--recovery-danger)] focus:outline-none"
                  aria-label="Number of rows to delete"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button
                  isDisabled={
                    Number(confirmCount) !== selectedIds.size || deleting
                  }
                  onPress={() => void confirmDelete()}
                >
                  {deleting ? 'Deleting…' : 'Confirm deletion'}
                </Button>
                <Button
                  variant="ghost"
                  isDisabled={deleting}
                  onPress={() => setConfirmOpen(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : null}
          <DataTable
            records={records}
            columns={columns}
            exportFileName="collection-follow-up"
            emptyMessage="No entry recorded."
            toolbarActions={
              <>
                {restoreButton}
                <Button
                  variant="ghost"
                  isDisabled={selectedIds.size === 0 || deleting}
                  onPress={() => {
                    setConfirmCount('');
                    setConfirmOpen(true);
                  }}
                >
                  Delete ({selectedIds.size})
                </Button>
              </>
            }
          />
        </>
      ) : (
        <>
          {restorePanel}
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-sm text-[var(--text-muted)]">
              No entry recorded yet.
            </p>
            {restoreButton}
          </div>
        </>
      )}
    </div>
  );
}
