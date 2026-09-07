'use client';

import { useMemo } from 'react';

import type { SectionProps } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import {
  SCHEDULE_YEARS,
  buildFixedAssets,
  fixedAssetRecords,
} from '@/lib/comptabilite/fixedAssets/model';
import { PageTitle } from '@/components/layout/PageTitle';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import { HorizontalBarChart } from '@/components/dashboard/viz/HorizontalBarChart';
import { Treemap } from '@/components/dashboard/viz/Treemap';
import { TrendChart } from '@/components/dashboard/viz/TrendChart';
import { DataTable } from '@/components/dashboard/table/DataTable';
import type { DataTableColumn } from '@/components/dashboard/table/DataTable';

const yearsFormatter = new Intl.NumberFormat('fr-FR', {
  maximumFractionDigits: 1,
});

const percentFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 1,
});

const PAGE_HINT =
  'The asset register behind the balance sheet: what the company owns, what it has already written off, what it bought and sold in the period, and how much useful life is left.';

/** Below this much life left, the register is due for renewal. */
const RENEWAL_WARNING_YEARS = 3;

const ASSET_COLUMNS: DataTableColumn[] = [
  { key: 'asset_ref', label: 'Ref' },
  { key: 'asset_name', label: 'Asset' },
  { key: 'category', label: 'Category' },
  { key: 'asset_class', label: 'Class' },
  { key: 'site', label: 'Site' },
  { key: 'acquisition_date', label: 'Acquired' },
  {
    key: 'useful_life_years',
    label: 'Life (y)',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 0,
  },
  { key: 'gross', label: 'Gross', align: 'right', valueStyle: 'currency' },
  {
    key: 'accumulated',
    label: 'Depreciation',
    align: 'right',
    valueStyle: 'currency',
  },
  { key: 'net', label: 'Net', align: 'right', valueStyle: 'currency' },
  {
    key: 'remaining_years',
    label: 'Life left (y)',
    align: 'right',
    valueStyle: 'decimal',
    maximumFractionDigits: 1,
  },
];

export function FixedAssetsSection({ company, site, datasets }: SectionProps) {
  const records = useMemo(
    () => fixedAssetRecords(datasets.fixed_assets),
    [datasets.fixed_assets],
  );
  const view = useMemo(() => buildFixedAssets(records), [records]);

  const perimeterSuffix = company
    ? ` — ${formatEntityName(company.display_name)}`
    : site
      ? ` — ${formatEntityName(site.name)}`
      : '';

  const assetRows = useMemo(
    () =>
      view.assets.map((asset) => ({
        asset_ref: asset.asset_ref,
        asset_name: asset.asset_name,
        category: asset.category_label,
        asset_class: asset.asset_class_label,
        site: asset.site,
        acquisition_date: asset.acquisition_date,
        useful_life_years: asset.useful_life_years,
        gross: asset.gross_value,
        accumulated: asset.accumulated_depreciation,
        net: asset.net_value,
        remaining_years: Math.round((asset.remaining_months / 12) * 10) / 10,
      })),
    [view.assets],
  );

  const treemapGroups = useMemo(
    () =>
      view.classes.map((assetClass) => ({
        key: assetClass.key,
        label: assetClass.label,
        value: assetClass.amount,
        leaves: view.assets
          .filter((asset) => asset.asset_class === assetClass.key && asset.net_value > 0)
          .map((asset) => ({
            key: asset.asset_ref,
            label: asset.asset_name,
            value: asset.net_value,
          })),
      })),
    [view.classes, view.assets],
  );

  if (records.length === 0) {
    return (
      <div className="fade-in">
        <div className="mb-8">
          <PageTitle hint={PAGE_HINT}>Fixed Assets{perimeterSuffix}</PageTitle>
        </div>
        <div className="glass rounded-lg p-6">
          <p className="text-sm text-[var(--text-muted)]">
            No asset register for this perimeter.
          </p>
        </div>
      </div>
    );
  }

  const { kpis } = view;

  return (
    <div className="fade-in">
      <div className="mb-8">
        <PageTitle hint={PAGE_HINT}>Fixed Assets{perimeterSuffix}</PageTitle>
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          {kpis.assetCount} assets in {view.categories.length} categories · register
          as of {view.asOfLabel}
        </p>
      </div>

      {/* ---- KPI cards ---------------------------------------------------- */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard
          label="Gross Value"
          value={kpis.gross}
          valueStyle="currency"
          subtitle="Acquisition cost held"
          hint="What the assets on the register cost when they were bought, before any depreciation. It only falls when something is disposed of."
        />
        <KpiCard
          label="Net Value"
          value={kpis.net}
          valueStyle="currency"
          subtitle="Book value on the balance sheet"
          hint="Gross value less accumulated depreciation — the figure carried on the balance sheet's Intangible assets and Property, plant & equipment lines."
        />
        <KpiCard
          label="Depreciation"
          value={kpis.accumulated}
          valueStyle="currency"
          tone="orange"
          subtitle={
            kpis.depreciationRate !== null
              ? `${percentFormatter.format(kpis.depreciationRate)} of gross written off`
              : 'Written off to date'
          }
          hint="Depreciation charged against the register since acquisition. A high share of gross means an ageing base, not a loss."
        />
        <KpiCard
          label="Acquisitions"
          value={kpis.acquisitions}
          valueStyle="currency"
          tone={kpis.acquisitions > 0 ? 'success' : 'default'}
          subtitle="Capitalised in the period"
          hint="Assets capitalised during the selected period, at cost. A flow — it sums across the window, unlike the values above."
        />
        <KpiCard
          label="Disposals"
          value={kpis.disposals}
          valueStyle="currency"
          subtitle="Net book value written off"
          hint="What the assets that left the register were still worth when they went. Disposing of a fully depreciated asset shows nothing here, and that is correct."
        />
        <KpiCard
          label="Remaining Useful Life"
          value={kpis.remainingLife ?? 0}
          valueStyle="decimal"
          maximumFractionDigits={1}
          displayValue={
            kpis.remainingLife === null
              ? '—'
              : `${yearsFormatter.format(kpis.remainingLife)} y`
          }
          tone={
            kpis.remainingLife === null
              ? 'default'
              : kpis.remainingLife < RENEWAL_WARNING_YEARS
                ? 'warning'
                : 'success'
          }
          subtitle={`${kpis.fullyDepreciated} fully depreciated`}
          hint="Mean life left across the register, weighted by net book value — so the assets that still carry value drive it. This is what tells you when capex comes due."
        />
      </div>

      {/* ---- Visualisations ---------------------------------------------- */}
      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TrendChart
          title="Depreciation Schedule"
          hint={`Depreciation the assets held today are already committed to, over the next ${SCHEDULE_YEARS} years. No new capex is assumed, so the taper is the register ageing out.`}
          labels={view.schedule.map((year) => year.year)}
          series={[
            {
              name: 'Charge',
              color: 'var(--recovery-orange)',
              values: view.schedule.map((year) => year.amount),
              fill: true,
            },
          ]}
          emptyMessage="No depreciation left to run on this register."
        />
        <HorizontalBarChart
          title="Asset Categories"
          items={view.categories.map((category) => ({
            label: category.label,
            amount: category.amount,
            count: category.count,
          }))}
          visibleCount={5}
          countNoun="asset"
          emptyMessage="No assets for this perimeter."
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4">
        <TrendChart
          title="Asset Evolution"
          hint="Gross cost against net book value, month by month. The widening gap is depreciation accumulating; the steps up are acquisitions."
          labels={view.evolution.map((point) => point.label)}
          series={[
            {
              name: 'Gross',
              color: 'var(--secondary)',
              values: view.evolution.map((point) => point.gross),
            },
            {
              name: 'Net',
              color: 'var(--primary)',
              values: view.evolution.map((point) => point.net),
              fill: true,
            },
          ]}
        />
      </div>

      <div className="mb-8">
        <Treemap
          title="Asset Distribution"
          hint="Net book value by class, then by asset. Area is proportional to value, so the biggest tile is the asset carrying the most book value."
          groups={treemapGroups}
          emptyMessage="No assets with book value for this perimeter."
        />
      </div>

      {/* ---- Register ------------------------------------------------------- */}
      <div className="mb-4">
        <PageTitle
          className="mb-4"
          hint="The register as of the latest month in the selected period, largest net value first."
        >
          Asset Register
        </PageTitle>
      </div>

      <DataTable
        records={assetRows}
        columns={ASSET_COLUMNS}
        emptyMessage="No assets for this perimeter."
        paginate
        defaultPageSize={20}
        globalSearch
        globalSearchPlaceholder="Search an asset, category or site…"
        summaryRow
        exportable
        exportFileName="asset-register"
      />

      <p className="mt-3 text-xs text-[var(--text-muted)]">
        Gross, net and accumulated depreciation are read as of {view.asOfLabel} — an
        asset held all year is one line, not twelve. Acquisitions, disposals and the
        depreciation charge aggregate across the selected period.
      </p>
    </div>
  );
}
