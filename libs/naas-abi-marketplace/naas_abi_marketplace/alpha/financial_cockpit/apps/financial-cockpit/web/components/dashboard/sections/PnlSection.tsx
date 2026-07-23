'use client';

import { Fragment, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { perimeterSlugsFor } from '@/lib/pnl/perimeter';
import {
  buildPnlStatement,
  categorie3Options,
  pnlRecords,
  type PnlAdjustment,
  type PnlBudgetRow,
  type PnlCategoryRow,
  type PnlCell,
  type PnlGranularity,
  type PnlLine,
  type PnlRecord,
  GRANULARITY_LABELS,
} from '@/lib/pnl/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/KpiCard';
import { Categorie3Filter } from '@/components/pnl/Categorie3Filter';
import { DataTable } from '@/components/dashboard/DataTable';
import type { DataTableColumn } from '@/components/dashboard/DataTable';

const GRANULARITIES: PnlGranularity[] = ['year', 'quarter', 'month'];

const currencyFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

function formatAmount(value: number): string {
  return currencyFormatter.format(value);
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : percentFormatter.format(value);
}

function amountClassName(value: number): string {
  return value < 0 ? 'text-red-500' : 'text-[var(--text)]';
}

/** Corporate sub-groups nest under the CHARGES CORPORATE total; every other
 * line renders at the top level. */
function visibleLines(lines: PnlLine[], expanded: ReadonlySet<string>): PnlLine[] {
  const corporateOpen = expanded.has('charges_corporate');
  return lines.filter((line) => {
    if (line.kind === 'group' && line.nested) {
      return corporateOpen;
    }
    return true;
  });
}

function invoiceDetailColumns(): DataTableColumn[] {
  return [
    { key: 'date', label: 'Date' },
    { key: 'company', label: 'Société' },
    { key: 'thirdparty', label: 'Tiers' },
    { key: 'categorie_3', label: 'Catégorie 3' },
    { key: 'invoice_number', label: 'Pièce' },
    { key: 'invoice_label', label: 'Libellé' },
    {
      key: 'amount',
      label: 'Montant',
      align: 'right' as const,
      valueStyle: 'currency' as const,
    },
  ];
}

function CellPair({ cell, budgetEnabled }: { cell: PnlCell; budgetEnabled: boolean }) {
  const variance = cell.budget !== 0 ? cell.actual - cell.budget : null;
  return (
    <>
      <td className={`px-3 py-1.5 text-right whitespace-nowrap ${amountClassName(cell.actual)}`}>
        {formatAmount(cell.actual)}
      </td>
      {budgetEnabled ? (
        <>
          <td className="px-3 py-1.5 text-right whitespace-nowrap text-[var(--text-muted)]">
            {formatAmount(cell.budget)}
          </td>
          <td
            className={`px-3 py-1.5 text-right whitespace-nowrap ${
              variance === null
                ? 'text-[var(--text-muted)]'
                : variance >= 0
                  ? 'text-emerald-500'
                  : 'text-red-500'
            }`}
          >
            {variance === null ? '—' : formatAmount(variance)}
          </td>
        </>
      ) : null}
    </>
  );
}

type RowKind = 'group' | 'total' | 'percent' | 'category';

function rowLabelClassName(kind: RowKind, nested: boolean): string {
  if (kind === 'total') {
    return 'font-semibold uppercase text-xs tracking-wide';
  }
  if (kind === 'percent') {
    return 'italic text-[var(--text-muted)] text-xs';
  }
  if (kind === 'category') {
    return nested ? 'pl-12 text-sm' : 'pl-8 text-sm';
  }
  return nested ? 'pl-6 font-medium text-sm' : 'font-semibold text-sm';
}

export function PnlSection(props: SectionProps) {
  return (
    <Suspense fallback={null}>
      <PnlSectionContent {...props} />
    </Suspense>
  );
}

function PnlSectionContent({ entity, company, site, datasets }: SectionProps) {
  const rawRecords = useMemo(() => pnlRecords(datasets.actuals), [datasets.actuals]);
  const perimeterSlugs = useMemo(
    () => perimeterSlugsFor(entity, company),
    [entity, company],
  );

  const [adjustments, setAdjustments] = useState<PnlAdjustment[]>([]);
  const [budgetRows, setBudgetRows] = useState<PnlBudgetRow[]>([]);
  const [granularity, setGranularity] = useState<PnlGranularity>('year');
  const [categorie3Filter, setCategorie3Filter] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedCategory, setSelectedCategory] = useState<{
    key: string;
    label: string;
    records: PnlRecord[];
  } | null>(null);
  const drillRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void fetch(`/api/entities/${entity.url_slug}/pnl/adjustments`)
      .then((response) => (response.ok ? response.json() : { records: [] }))
      .then((body) => {
        if (!cancelled) {
          setAdjustments(Array.isArray(body.records) ? body.records : []);
        }
      })
      .catch(() => undefined);
    void fetch(`/api/entities/${entity.url_slug}/pnl/budget`)
      .then((response) => (response.ok ? response.json() : { records: [] }))
      .then((body) => {
        if (!cancelled) {
          setBudgetRows(Array.isArray(body.records) ? body.records : []);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [entity.url_slug]);

  const scenarioId = useSearchParams().get('scenario');

  const categorie3Choices = useMemo(() => categorie3Options(rawRecords), [rawRecords]);

  const statement = useMemo(
    () =>
      buildPnlStatement(rawRecords, adjustments, budgetRows, {
        scenarioId,
        granularity,
        categorie3Filter,
        perimeterSlugs,
      }),
    [rawRecords, adjustments, budgetRows, scenarioId, granularity, categorie3Filter, perimeterSlugs],
  );

  function toggleExpanded(key: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function onSelectCategory(groupKey: string, category: PnlCategoryRow) {
    setSelectedCategory({
      key: `${groupKey}:${category.key}`,
      label: category.label,
      records: category.records,
    });
    window.requestAnimationFrame(() => {
      drillRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const rows = visibleLines(statement.lines, expanded);
  const { budgetEnabled } = statement;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint="Compte de résultat consolidé depuis les actuals (Ventes, Travaux, Charges, Corporate).">
          Compte de Résultat{perimeterSuffix}
        </PageTitle>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="CA vs Budget"
          value={statement.kpis.ventes.actual}
          valueStyle="currency"
          tone="success"
          subtitle={`Budget : ${formatAmount(statement.kpis.ventes.budget)}`}
          hint="Ventes + Travaux réalisés sur la période comparés au budget."
        />
        <KpiCard
          label="Charges vs Budget"
          value={statement.kpis.charges.actual}
          valueStyle="currency"
          tone="danger"
          subtitle={`Budget : ${formatAmount(statement.kpis.charges.budget)}`}
          hint="Charges d'exploitation + corporate réalisées comparées au budget."
        />
        <KpiCard
          label="Marge Brute"
          value={statement.kpis.margeBrute.actual}
          valueStyle="currency"
          subtitle={`${formatPercent(statement.kpis.margeBrutePct)} du CA — Budget : ${formatAmount(
            statement.kpis.margeBrute.budget,
          )}`}
          hint="Ventes + Travaux moins charges directes."
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1 rounded-md border border-[var(--border)] bg-[var(--accent)] p-1">
          {GRANULARITIES.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setGranularity(option)}
              className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                granularity === option
                  ? 'bg-[var(--secondary)] text-white'
                  : 'text-[var(--text-muted)] hover:text-[var(--text)]'
              }`}
            >
              {GRANULARITY_LABELS[option]}
            </button>
          ))}
        </div>
        <Categorie3Filter
          options={categorie3Choices}
          selected={categorie3Filter}
          onChange={setCategorie3Filter}
        />
      </div>

      {!budgetEnabled ? (
        <p className="mb-3 text-xs text-[var(--text-muted)]">
          Le budget n&apos;est pas disponible lorsqu&apos;un filtre Catégorie 3 est actif.
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-white">
                Ligne
              </th>
              {statement.periods.map((period) => (
                <th
                  key={period.id}
                  colSpan={budgetEnabled ? 3 : 1}
                  className="border-b border-l border-[var(--border)] bg-[var(--secondary)] px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap"
                >
                  {period.label}
                </th>
              ))}
              <th
                colSpan={budgetEnabled ? 3 : 1}
                className="border-b border-l border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_85%,black)] px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap"
              >
                Total
              </th>
            </tr>
            <tr>
              <th className="sticky left-0 z-10 border-b border-[var(--border)] bg-[var(--accent)]" />
              {statement.periods.map((period) => (
                <Fragment key={period.id}>
                  <th className="border-b border-l border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-right text-[11px] font-semibold text-[var(--text-muted)]">
                    Actuel
                  </th>
                  {budgetEnabled ? (
                    <>
                      <th className="border-b border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-right text-[11px] font-semibold text-[var(--text-muted)]">
                        Budget
                      </th>
                      <th className="border-b border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-right text-[11px] font-semibold text-[var(--text-muted)]">
                        Act vs Bud
                      </th>
                    </>
                  ) : null}
                </Fragment>
              ))}
              <th className="border-b border-l border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-right text-[11px] font-semibold text-[var(--text-muted)]">
                Actuel
              </th>
              {budgetEnabled ? (
                <>
                  <th className="border-b border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-right text-[11px] font-semibold text-[var(--text-muted)]">
                    Budget
                  </th>
                  <th className="border-b border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-right text-[11px] font-semibold text-[var(--text-muted)]">
                    Act vs Bud
                  </th>
                </>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((line) => {
              if (line.kind === 'percent') {
                return (
                  <tr key={line.key} className="border-b border-[var(--border)]">
                    <td
                      className={`sticky left-0 z-10 bg-[var(--surface)] px-3 py-1 ${rowLabelClassName(
                        'percent',
                        false,
                      )}`}
                    >
                      {line.label}
                    </td>
                    {line.periods.map((value, index) => (
                      <td
                        key={`${line.key}-${index}`}
                        colSpan={budgetEnabled ? 3 : 1}
                        className="border-l border-[var(--border)] px-3 py-1 text-right text-[var(--text-muted)]"
                      >
                        {formatPercent(value)}
                      </td>
                    ))}
                    <td
                      colSpan={budgetEnabled ? 3 : 1}
                      className="border-l border-[var(--border)] px-3 py-1 text-right font-medium text-[var(--text-muted)]"
                    >
                      {formatPercent(line.total)}
                    </td>
                  </tr>
                );
              }

              if (line.kind === 'total') {
                const expandable = line.key === 'charges_corporate';
                return (
                  <tr
                    key={line.key}
                    className="border-b border-t border-[var(--border)] bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))]"
                  >
                    <td
                      className={`sticky left-0 z-10 bg-[color-mix(in_srgb,var(--secondary)_6%,var(--surface))] px-3 py-2 ${rowLabelClassName(
                        'total',
                        false,
                      )}`}
                    >
                      {expandable ? (
                        <button
                          type="button"
                          onClick={() => toggleExpanded(line.key)}
                          className="mr-2 inline-flex h-4 w-4 items-center justify-center align-middle text-[var(--text-muted)]"
                          aria-label={expanded.has(line.key) ? 'Réduire' : 'Développer'}
                        >
                          {expanded.has(line.key) ? '▾' : '▸'}
                        </button>
                      ) : null}
                      {line.label}
                    </td>
                    {line.cells.periods.map((cell, index) => (
                      <CellPair key={`${line.key}-${index}`} cell={cell} budgetEnabled={budgetEnabled} />
                    ))}
                    <CellPair cell={line.cells.total} budgetEnabled={budgetEnabled} />
                  </tr>
                );
              }

              // kind === 'group'
              const isOpen = expanded.has(line.key);
              return (
                <Fragment key={line.key}>
                  <tr className="border-b border-[var(--border)]">
                    <td
                      className={`sticky left-0 z-10 bg-[var(--surface)] px-3 py-1.5 ${rowLabelClassName(
                        'group',
                        line.nested,
                      )}`}
                    >
                      <button
                        type="button"
                        onClick={() => toggleExpanded(line.key)}
                        className="mr-2 inline-flex h-4 w-4 items-center justify-center align-middle text-[var(--text-muted)]"
                        aria-label={isOpen ? 'Réduire' : 'Développer'}
                      >
                        {isOpen ? '▾' : '▸'}
                      </button>
                      {line.label}
                    </td>
                    {line.cells.periods.map((cell, index) => (
                      <CellPair key={`${line.key}-${index}`} cell={cell} budgetEnabled={budgetEnabled} />
                    ))}
                    <CellPair cell={line.cells.total} budgetEnabled={budgetEnabled} />
                  </tr>
                  {isOpen
                    ? line.categories.map((category) => (
                        <tr
                          key={category.key}
                          className={`cursor-pointer border-b border-[var(--border)] transition-colors hover:bg-[var(--accent)] ${
                            selectedCategory?.key === `${line.key}:${category.key}`
                              ? 'bg-[var(--accent)]'
                              : ''
                          }`}
                          onClick={() => onSelectCategory(line.key, category)}
                        >
                          <td
                            className={`sticky left-0 z-10 bg-[var(--surface)] px-3 py-1 text-[var(--text-muted)] ${rowLabelClassName(
                              'category',
                              line.nested,
                            )}`}
                          >
                            {category.label}
                          </td>
                          {category.cells.periods.map((cell, index) => (
                            <CellPair
                              key={`${category.key}-${index}`}
                              cell={cell}
                              budgetEnabled={budgetEnabled}
                            />
                          ))}
                          <CellPair cell={category.cells.total} budgetEnabled={budgetEnabled} />
                        </tr>
                      ))
                    : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedCategory ? (
        <div ref={drillRef} className="mt-8 scroll-mt-6">
          <PageTitle className="mb-4">
            Lignes actuals — {selectedCategory.label}
          </PageTitle>
          <DataTable
            records={selectedCategory.records as unknown as Record<string, unknown>[]}
            columns={invoiceDetailColumns()}
            summaryRow
            exportFileName="pnl-detail"
            emptyMessage="Aucune ligne pour cette catégorie."
          />
        </div>
      ) : null}
    </div>
  );
}
