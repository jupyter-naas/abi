'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { CompanyConfig, SectionProps } from '@/lib/types';
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
  { key: 'company', label: 'Société' },
  { key: 'site', label: 'Projet' },
  { key: 'client', label: 'Client' },
  { key: 'categorie_2', label: 'Catégorie analytique' },
  { key: 'invoice_ref', label: 'N° facture' },
  { key: 'due_date', label: 'Échéance' },
  {
    key: 'recovery_action_label',
    label: 'Statut relance',
    renderValue: renderRecoveryLabel,
  },
  {
    key: 'remaining_amount_ttc',
    label: 'Impayé TTC',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
  {
    key: 'amount_ttc',
    label: 'Montant TTC',
    align: 'right' as const,
    valueStyle: 'currency' as const,
  },
  {
    key: 'days_overdue',
    label: 'Retard (j)',
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
  date_relance: 'Date relance',
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
            label: 'Date relance',
            renderCell: (row: Record<string, unknown>) => {
              const target = annotationTarget(row);
              return (
                <InvoiceAnnotationCell
                  type="date"
                  value={typeof row.date_relance === 'string' ? row.date_relance : ''}
                  ariaLabel={`Date de relance — facture ${target.invoiceNumber}`}
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
            ariaLabel={`Notes — facture ${target.invoiceNumber}`}
            placeholder="Ajouter une note"
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

  const pageHint = `Suivi des factures émises non encore réglées : ancienneté, montants et statut de relance — ${formatEntityName(entity.display_name)}`;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={pageHint}>
          Impayés Clients
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
                label="Facturé"
                value={summary.invoiced_amount_ttc}
                valueStyle="currency"
                subtitle={
                  summary.invoice_count
                    ? `${summary.invoice_count} facture(s) · montant TTC`
                    : 'Montant TTC'
                }
                hint="Total TTC facturé sur le périmètre (toutes factures autorisées)."
              />
              <KpiCard
                label="Impayés en cours"
                value={recoveryKpis.en_cours.amount}
                valueStyle="currency"
                hint={recoveryRulesHint()}
                subtitle={`${recoveryKpis.en_cours.count} facture(s)`}
                onAction={
                  recoveryKpis.en_cours.count > 0
                    ? () => openDetailTable('all')
                    : undefined
                }
                actionLabel="Voir toutes les factures impayées"
              />
              <KpiCard
                label="Taux de recouvrement"
                value={summary.recovery_rate}
                valueStyle="percent"
                percentInput="rate"
                maximumFractionDigits={1}
                tone="success"
                hint="(Facturé TTC − impayés TTC) / facturé TTC sur le périmètre filtré."
              />
            </div>
          ) : null}
          {recoveryKpis.en_cours.count > 0 ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <KpiCard
                label="Relance téléphonique"
                value={recoveryKpis.relance_telephonique.amount}
                valueStyle="currency"
                tone="warning"
                hint={recoveryRuleHint('Relance téléphonique')}
                subtitle={`${recoveryKpis.relance_telephonique.count} facture(s)`}
                onAction={() => openDetailTable('relance_telephonique')}
                actionLabel="Filtrer sur Relance téléphonique"
              />
              <KpiCard
                label="Mise en demeure"
                value={recoveryKpis.mise_en_demeure.amount}
                valueStyle="currency"
                tone="orange"
                hint={recoveryRuleHint('Mise en demeure')}
                subtitle={`${recoveryKpis.mise_en_demeure.count} facture(s)`}
                onAction={() => openDetailTable('mise_en_demeure')}
                actionLabel="Filtrer sur Mise en demeure"
              />
              <KpiCard
                label="Arbitrage"
                value={recoveryKpis.arbitrage.amount}
                valueStyle="currency"
                tone="danger"
                hint={recoveryRuleHint('Arbitrage')}
                subtitle={`${recoveryKpis.arbitrage.count} facture(s)`}
                onAction={() => openDetailTable('arbitrage')}
                actionLabel="Filtrer sur Arbitrage"
              />
            </div>
          ) : null}
        </div>
      ) : summary ? (
        <div className="glass rounded-lg p-6 mb-8">
          <p className="text-sm text-[var(--text-muted)]">
            Aucun impayé en cours{dataAsOf ? ` au ${dataAsOf}` : ''}.
          </p>
        </div>
      ) : null}

      {recoveryKpis.mise_en_demeure.count > 0 || recoveryKpis.arbitrage.count > 0 ? (
        <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <HorizontalBarChart
            title="Mise en demeure par client"
            items={mise_en_demeure_by_client}
            emptyMessage="Aucun impayé en mise en demeure par client."
          />
          <HorizontalBarChart
            title="Arbitrage par client"
            items={arbitrage_by_client}
            emptyMessage="Aucun impayé en arbitrage par client."
          />
        </div>
      ) : null}

      {tableInvoices.length > 0 ? (
        <div ref={detailTableRef} className="mb-8 scroll-mt-6">
          <PageTitle className="mb-6">Détail des factures</PageTitle>
          <DataTable
            records={detailRecords}
            columns={detailTableColumns}
            columnFilters={detailFilters}
            onColumnFiltersChange={setDetailFilters}
            showAllRows={detailShowAllRows}
            onShowAllRowsChange={setDetailShowAllRows}
            exportFileName="impayes-clients"
            emptyMessage="Aucune facture pour ce périmètre."
          />
        </div>
      ) : (
        <div ref={detailTableRef} className="mb-8 scroll-mt-6">
          <PageTitle className="mb-6">Détail des factures</PageTitle>
          <p className="text-sm text-[var(--text-muted)]">
            Aucune facture pour ce périmètre à la date d&apos;extraction.
          </p>
        </div>
      )}

      <RelanceLogSection
        entitySlug={entity.url_slug}
        entries={annotationHistory}
        joinInfo={invoiceLogJoinInfo}
        companyFilter={company}
        showCompanyColumn={showCompanyColumn}
        isAdmin={user.role === 'admin'}
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
  /** Same visibility rule as the detail table's Société column. */
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
        label: 'Sél.',
        renderHeader: () => (
          <input
            type="checkbox"
            className={logCheckboxClass}
            checked={allSelected}
            disabled={selectableIds.length === 0}
            aria-label="Tout sélectionner"
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
              aria-label={`Sélectionner la ligne ${String(row.invoice_number ?? '')}`}
              onChange={() => toggleOne(eventId)}
            />
          );
        },
      },
      { key: 'date_edited', label: 'Modifié le' },
      { key: 'user', label: 'Utilisateur' },
      ...(showCompanyColumn ? [{ key: 'company', label: 'Société' }] : []),
      { key: 'site', label: 'Projet' },
      { key: 'client', label: 'Client' },
      { key: 'categorie_2', label: 'Catégorie analytique' },
      { key: 'invoice_number', label: 'N° facture' },
      {
        key: 'status_relance',
        label: 'Statut relance',
        renderValue: renderRecoveryLabel,
      },
      { key: 'field', label: 'Champ' },
      {
        key: 'value',
        label: 'Valeur',
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
              ariaLabel={`Valeur — facture ${String(row.invoice_number ?? '')}`}
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
      Restaurer l&apos;historique
    </Button>
  ) : null;

  const restorePanel =
    isAdmin && restoreOpen ? (
      <div className="mb-4 flex flex-col gap-3 border border-[var(--border)] bg-[var(--accent)] p-4 text-sm">
        <p className="text-[var(--text)]">
          Restaure les événements sauvegardés (dossier backup) dans le journal.
          Les événements déjà présents sont conservés et la sauvegarde n&apos;est
          pas modifiée. Laissez la date vide pour restaurer tout l&apos;historique.
        </p>
        <label className="flex flex-wrap items-center gap-2 text-[var(--text)]">
          À partir du (optionnel) :
          <input
            type="datetime-local"
            value={restoreFrom}
            onChange={(event) => setRestoreFrom(event.target.value)}
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)] focus:border-[var(--secondary)] focus:outline-none"
            aria-label="Restaurer à partir de cette date"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button isDisabled={restoring} onPress={() => void restoreHistory()}>
            {restoring ? 'Restauration…' : 'Restaurer'}
          </Button>
          <Button
            variant="ghost"
            isDisabled={restoring}
            onPress={() => setRestoreOpen(false)}
          >
            Annuler
          </Button>
        </div>
      </div>
    ) : null;

  return (
    <div className="mb-8">
      <PageTitle
        className="mb-6"
        hint="Historique des saisies (date de relance et notes) effectuées dans le détail des factures. La valeur reste modifiable ligne par ligne ; la sélection permet une suppression en masse."
      >
        Suivi relance
      </PageTitle>
      {records.length > 0 ? (
        <>
          {restorePanel}
          {confirmOpen && selectedIds.size > 0 ? (
            <div className="mb-4 flex flex-col gap-3 border border-[var(--recovery-danger)] bg-[color-mix(in_srgb,var(--recovery-danger)_8%,var(--surface))] p-4 text-sm">
              <p className="font-medium text-[var(--recovery-danger)]">
                ⚠️ Vous êtes sur le point de supprimer définitivement{' '}
                {selectedIds.size} ligne(s) du journal. Les valeurs affichées dans le
                détail des factures seront recalculées sans ces événements. Cette
                action est irréversible.
              </p>
              <label className="flex flex-wrap items-center gap-2 text-[var(--text)]">
                Saisissez le nombre de lignes à supprimer pour confirmer :
                <input
                  type="number"
                  min={0}
                  value={confirmCount}
                  onChange={(event) => setConfirmCount(event.target.value)}
                  className="w-24 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)] focus:border-[var(--recovery-danger)] focus:outline-none"
                  aria-label="Nombre de lignes à supprimer"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <Button
                  isDisabled={
                    Number(confirmCount) !== selectedIds.size || deleting
                  }
                  onPress={() => void confirmDelete()}
                >
                  {deleting ? 'Suppression…' : 'Confirmer la suppression'}
                </Button>
                <Button
                  variant="ghost"
                  isDisabled={deleting}
                  onPress={() => setConfirmOpen(false)}
                >
                  Annuler
                </Button>
              </div>
            </div>
          ) : null}
          <DataTable
            records={records}
            columns={columns}
            exportFileName="suivi-relance"
            emptyMessage="Aucune saisie enregistrée."
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
                  Supprimer ({selectedIds.size})
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
              Aucune saisie enregistrée pour le moment.
            </p>
            {restoreButton}
          </div>
        </>
      )}
    </div>
  );
}
