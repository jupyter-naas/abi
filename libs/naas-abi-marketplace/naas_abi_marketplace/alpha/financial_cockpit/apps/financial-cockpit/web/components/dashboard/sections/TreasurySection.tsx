'use client';

import { useCallback, useMemo, useRef, useState } from 'react';

import type { SectionProps } from '@/lib/types';
import { isConsolidation } from '@/lib/config/entityHelpers';
import {
  breakdownForDay,
  breakdownForType,
  buildCashBridge,
  buildCashProjection,
  isTreasuryDataset,
  signedAmount,
  sumByType,
  treasuryItems,
  TYPE_COLOR,
  TYPE_LABELS,
  type BreakdownDimension,
  type CashBridgeStep,
  type CashProjectionPoint,
  type TreasuryItem,
  type TreasuryItemType,
} from '@/lib/data/treasury';
import { serializeColumnFilter } from '@/lib/table/columnFilterUtils';
import { PageTitle } from '@/components/layout/PageTitle';
import { CashBridgeChart } from '@/components/dashboard/CashBridgeChart';
import { CashProjectionChart } from '@/components/dashboard/CashProjectionChart';
import { AccountBarChart } from '@/components/dashboard/AccountBarChart';
import { PennylaneLinkCell } from '@/components/dashboard/PennylaneLinkCell';
import { InvoiceActionsCell } from '@/components/dashboard/InvoiceActionsCell';
import { DataTable } from '@/components/dashboard/DataTable';
import type { DataTableColumn } from '@/components/dashboard/DataTable';

function buildTableColumns(entitySlug: string): DataTableColumn[] {
  return [
    { key: 'company', label: 'Société' },
    { key: 'type_label', label: 'Type' },
    { key: 'label', label: 'Libellé' },
    { key: 'categorie_2', label: 'Catégorie analytique' },
    { key: 'meta', label: 'Tiers' },
    { key: 'date', label: 'Date' },
    { key: 'deadline', label: 'Échéance' },
    {
      key: 'amount',
      label: 'Montant TTC',
      align: 'right' as const,
      valueStyle: 'currency' as const,
    },
    {
      key: '_actions',
      label: 'Actions',
      renderCell: (row) => {
        const invoiceId = typeof row.invoice_id === 'string' ? row.invoice_id : null;
        const organizationSlug =
          typeof row.organization_slug === 'string'
            ? row.organization_slug
            : typeof row.entity_id === 'string'
              ? row.entity_id
              : null;
        // Bank position rows carry no invoice — nothing to download/view/link.
        if (!invoiceId || !organizationSlug) {
          return (
            <PennylaneLinkCell
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
              invoiceRef={typeof row.invoice_ref === 'string' ? row.invoice_ref : null}
            />
          );
        }
        return (
          <InvoiceActionsCell
            entitySlug={entitySlug}
            invoiceId={invoiceId}
            organizationSlug={organizationSlug}
            invoiceType={row.type === 'upcoming_disbursement' ? 'supplier' : 'customer'}
            invoiceRef={typeof row.invoice_ref === 'string' ? row.invoice_ref : null}
            pennylaneTransactionsUrl={
              typeof row.pennylane_transactions_url === 'string'
                ? row.pennylane_transactions_url
                : null
            }
            pennylaneCompanyId={
              typeof row.pennylane_company_id === 'number' ? row.pennylane_company_id : null
            }
          />
        );
      },
    },
  ];
}

const DIMENSION_LABEL: Record<BreakdownDimension, string> = {
  bank_account: 'compte bancaire',
  thirdparty: 'tiers',
  company: 'société',
};

const fullDateFormatter = new Intl.DateTimeFormat('fr-FR', {
  day: '2-digit',
  month: 'long',
  year: 'numeric',
});

function formatDayLabel(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  return fullDateFormatter.format(new Date(year, month - 1, day));
}

function dimensionFor(
  type: TreasuryItemType,
  allCompanies: boolean,
): BreakdownDimension {
  if (allCompanies) return 'company';
  return type === 'position' ? 'bank_account' : 'thirdparty';
}

export function TreasurySection({ entity, company, datasets }: SectionProps) {
  const [expandedStep, setExpandedStep] = useState<TreasuryItemType | null>('position');
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [tableFilters, setTableFilters] = useState<Record<string, string>>({});
  const [showAllRows, setShowAllRows] = useState(false);
  const tableRef = useRef<HTMLDivElement>(null);
  const breakdownRef = useRef<HTMLDivElement>(null);
  const projectionRef = useRef<HTMLDivElement>(null);

  const dataset = isTreasuryDataset(datasets.cash_position)
    ? datasets.cash_position
    : undefined;
  const items = useMemo(() => treasuryItems(dataset), [dataset]);
  const tableColumns = useMemo(() => buildTableColumns(entity.url_slug), [entity.url_slug]);
  const totals = useMemo(() => sumByType(items), [items]);
  const bridge = useMemo(() => buildCashBridge(items), [items]);
  const projection = useMemo(() => buildCashProjection(items), [items]);
  const positionDate = useMemo(
    () => items.find((item) => item.type === 'position')?.date ?? null,
    [items],
  );

  // "Toutes les sociétés" = a consolidation viewed without a company sub-filter.
  const allCompanies = isConsolidation(entity) && company === null;

  const activeType: TreasuryItemType | null = expandedStep;
  const dimension = activeType ? dimensionFor(activeType, allCompanies) : null;
  const breakdown = useMemo(
    () => (activeType ? breakdownForType(items, activeType, dimension!) : []),
    [items, activeType, dimension],
  );

  const selectedDay = useMemo(
    () =>
      selectedDate
        ? (projection.find((point) => point.date === selectedDate) ?? null)
        : null,
    [projection, selectedDate],
  );
  const dayBreakdown = useMemo(
    () => (selectedDay ? breakdownForDay(selectedDay) : null),
    [selectedDay],
  );

  const tableRecords = useMemo(
    () =>
      items.map((item: TreasuryItem) => ({
        ...item,
        company: item.company ?? '—',
        label: item.label ?? '—',
        meta: item.meta ?? '—',
        date: item.date ?? '—',
        deadline: item.deadline ?? '—',
        // Décaissement / avoir show as outflows (negative); position keeps its sign.
        amount: signedAmount(item),
      })),
    [items],
  );

  const onStepClick = useCallback(
    (step: CashBridgeStep) => {
      if (!step.type) return;
      // Second click on the same step → collapse the drill-down and clear the filter.
      if (expandedStep === step.type) {
        setExpandedStep(null);
        setTableFilters({});
        return;
      }
      // First click → drill-down chart (scroll here first) + filter the detail table.
      setExpandedStep(step.type);
      setSelectedDate(null);
      setTableFilters({ type_label: step.label });
      setShowAllRows(true);
      window.requestAnimationFrame(() => {
        breakdownRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    },
    [expandedStep],
  );

  const onProjectionPointClick = useCallback(
    (point: CashProjectionPoint) => {
      // Second click on the same day → collapse the drill-down and clear the filter.
      if (selectedDate === point.date) {
        setSelectedDate(null);
        setTableFilters({});
        return;
      }
      // First click → per-day drill-down + filter the detail table on the
      // échéances of that day's movements (past-due lines collapsed onto
      // today keep their original échéance).
      setSelectedDate(point.date);
      setExpandedStep(null);
      const deadlines = new Set(
        point.entries
          .map((entry) => entry.deadline)
          .filter((value): value is string => Boolean(value)),
      );
      setTableFilters(
        deadlines.size > 0 ? { deadline: serializeColumnFilter(deadlines) } : {},
      );
      setShowAllRows(true);
      window.requestAnimationFrame(() => {
        projectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    },
    [selectedDate],
  );

  const breakdownTitle =
    activeType && dimension
      ? `${TYPE_LABELS[activeType]} par ${DIMENSION_LABEL[dimension]}`
      : '';

  return (
    <div className="fade-in">
      {/* Projected cash line — today → latest échéance, red below zero. */}
      {projection.length > 1 ? (
        <div ref={projectionRef} className="mb-10 scroll-mt-6">
          <PageTitle
            className="mb-4"
            hint="Solde bancaire courant projeté jour par jour jusqu'à la dernière échéance : encaissements (+) et décaissements (−). Cliquez un point pour détailler les encaissements et décaissements du jour et filtrer le tableau ; recliquez pour réinitialiser."
          >
            Projection jour par jour
          </PageTitle>
          <CashProjectionChart
            points={projection}
            initialPosition={totals.position.amount}
            positionDate={positionDate}
            onPointClick={onProjectionPointClick}
            activeDate={selectedDate}
          />
          {selectedDay && dayBreakdown ? (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <AccountBarChart
                title={`Encaissement — ${formatDayLabel(selectedDay.date)}`}
                hint="Recliquez le point du graphique pour réinitialiser le tableau."
                items={dayBreakdown.encaissements}
                color={TYPE_COLOR.upcoming_collection}
                emptyMessage="Aucun encaissement ce jour."
              />
              <AccountBarChart
                title={`Décaissement — ${formatDayLabel(selectedDay.date)}`}
                hint="Recliquez le point du graphique pour réinitialiser le tableau."
                items={dayBreakdown.decaissements}
                color={TYPE_COLOR.upcoming_disbursement}
                emptyMessage="Aucun décaissement ce jour."
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Bridge — title, then the clickable waterfall. */}
      <div className="mb-10">
        <PageTitle
          className="mb-4"
          hint="Cliquez une étape pour la détailler et filtrer le tableau ; recliquez pour réinitialiser."
        >
          Bridge de trésorerie — actuel → prévisionnel
        </PageTitle>

        {items.length > 0 ? (
          <>
            <CashBridgeChart
              steps={bridge}
              onStepClick={onStepClick}
              activeStepKey={expandedStep ?? undefined}
            />
            {activeType ? (
              <div ref={breakdownRef} className="mt-4 scroll-mt-6">
                <AccountBarChart
                  title={breakdownTitle}
                  hint="Recliquez l'étape du bridge pour réinitialiser le tableau."
                  items={breakdown}
                  variant={activeType === 'position' ? 'diverging' : 'bar'}
                  color={activeType === 'position' ? undefined : TYPE_COLOR[activeType]}
                />
              </div>
            ) : null}
          </>
        ) : (
          <div className="glass rounded-lg p-6">
            <p className="text-sm text-[var(--text-muted)]">
              Aucune donnée de trésorerie pour ce périmètre.
            </p>
          </div>
        )}
      </div>

      {items.length > 0 ? (
        <div ref={tableRef} className="mb-8 scroll-mt-6">
          <PageTitle className="mb-6">Détail des lignes de trésorerie</PageTitle>
          <DataTable
            records={tableRecords}
            columns={tableColumns}
            columnFilters={tableFilters}
            onColumnFiltersChange={setTableFilters}
            showAllRows={showAllRows}
            onShowAllRowsChange={setShowAllRows}
            summaryRow
            exportFileName="tresorerie-detail"
            emptyMessage="Aucune ligne pour ce périmètre."
          />
        </div>
      ) : null}
    </div>
  );
}
