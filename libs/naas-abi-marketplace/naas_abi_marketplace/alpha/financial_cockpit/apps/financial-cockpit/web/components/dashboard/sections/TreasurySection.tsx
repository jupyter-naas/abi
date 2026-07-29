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
  typeLabelFor,
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
    { key: 'company', label: 'Company' },
    { key: 'type_label', label: 'Type' },
    { key: 'label', label: 'Description' },
    { key: 'categorie_2', label: 'Analytical category' },
    { key: 'meta', label: 'Thirdparty' },
    { key: 'date', label: 'Date' },
    { key: 'deadline', label: 'Due date' },
    {
      key: 'amount',
      label: 'Amount incl. tax',
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
  bank_account: 'bank account',
  thirdparty: 'thirdparty',
  company: 'company',
};

const fullDateFormatter = new Intl.DateTimeFormat('en-GB', {
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

  // "All companies" = a consolidation viewed without a company sub-filter.
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
        // Re-label from `type` so the column and the bridge drill-down filter
        // share the same English vocabulary as TYPE_LABELS.
        type_label: typeLabelFor(item),
        label: item.label ?? '—',
        meta: item.meta ?? '—',
        date: item.date ?? '—',
        deadline: item.deadline ?? '—',
        // Cash out / credit notes show as outflows (negative); position keeps its sign.
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
      // due dates of that day's movements (past-due lines collapsed onto
      // today keep their original due date).
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
      ? `${TYPE_LABELS[activeType]} by ${DIMENSION_LABEL[dimension]}`
      : '';

  return (
    <div className="fade-in">
      {/* Projected cash line — today → latest due date, red below zero. */}
      {projection.length > 1 ? (
        <div ref={projectionRef} className="mb-10 scroll-mt-6">
          <PageTitle
            className="mb-4"
            hint="Current bank balance projected day by day up to the last due date: cash in (+) and cash out (−). Click a point to break down that day's cash in and cash out and filter the table; click again to reset."
          >
            Day-by-day projection
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
                title={`Cash in — ${formatDayLabel(selectedDay.date)}`}
                hint="Click the chart point again to reset the table."
                items={dayBreakdown.encaissements}
                color={TYPE_COLOR.upcoming_collection}
                emptyMessage="No cash in on this day."
              />
              <AccountBarChart
                title={`Cash out — ${formatDayLabel(selectedDay.date)}`}
                hint="Click the chart point again to reset the table."
                items={dayBreakdown.decaissements}
                color={TYPE_COLOR.upcoming_disbursement}
                emptyMessage="No cash out on this day."
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Bridge — title, then the clickable waterfall. */}
      <div className="mb-10">
        <PageTitle
          className="mb-4"
          hint="Click a step to break it down and filter the table; click again to reset."
        >
          Cash bridge — actual → projected
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
                  hint="Click the bridge step again to reset the table."
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
              No cash data for this perimeter.
            </p>
          </div>
        )}
      </div>

      {items.length > 0 ? (
        <div ref={tableRef} className="mb-8 scroll-mt-6">
          <PageTitle className="mb-6">Cash line detail</PageTitle>
          <DataTable
            records={tableRecords}
            columns={tableColumns}
            columnFilters={tableFilters}
            onColumnFiltersChange={setTableFilters}
            showAllRows={showAllRows}
            onShowAllRowsChange={setShowAllRows}
            summaryRow
            exportFileName="cash-detail"
            emptyMessage="No line for this perimeter."
          />
        </div>
      ) : null}
    </div>
  );
}
