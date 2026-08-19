'use client';

import { useMemo } from 'react';

import {
  DataTable,
  type DataTableColumn,
} from '@/components/dashboard/table/DataTable';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import type { NumberDisplayStyle } from '@/lib/theme/typography';

export type AdminKpi = {
  label: string;
  value: number;
  valueStyle?: NumberDisplayStyle;
  currency?: string;
  maximumFractionDigits?: number;
  subtitle?: string;
  tone?: 'default' | 'success' | 'warning' | 'orange' | 'danger';
  /** Text shown in place of the number (for non-numeric metrics such as a date). */
  displayValue?: string;
};

type AdminSettingsPageProps = {
  /** One or two sentences: what this screen configures and who owns it. */
  description: string;
  kpis?: AdminKpi[];
  columns: DataTableColumn[];
  records: Record<string, unknown>[];
  /** Columns whose text values render as a coloured status badge. */
  statusColumns?: string[];
  emptyMessage?: string;
  exportFileName: string;
  defaultPageSize?: number;
};

type BadgeTone = 'success' | 'warning' | 'danger' | 'neutral';

/**
 * Status vocabularies across the settings datasets, mapped to the three
 * recovery tones. Anything unlisted renders neutral rather than guessing.
 */
const BADGE_TONES: Record<string, BadgeTone> = {
  active: 'success',
  connected: 'success',
  succeeded: 'success',
  closed: 'success',
  info: 'success',
  yes: 'success',
  open: 'warning',
  draft: 'warning',
  paused: 'warning',
  idle: 'warning',
  stale: 'warning',
  warning: 'warning',
  warn: 'warning',
  error: 'danger',
  failed: 'danger',
  blocking: 'danger',
  archived: 'neutral',
  protected: 'neutral',
  no: 'neutral',
};

const BADGE_CLASSES: Record<BadgeTone, string> = {
  success:
    'border-[var(--recovery-success)] text-[var(--recovery-success)] bg-[color-mix(in_srgb,var(--recovery-success)_12%,transparent)]',
  warning:
    'border-[var(--recovery-warning)] text-[var(--recovery-warning)] bg-[color-mix(in_srgb,var(--recovery-warning)_14%,transparent)]',
  danger:
    'border-[var(--recovery-danger)] text-[var(--recovery-danger)] bg-[color-mix(in_srgb,var(--recovery-danger)_12%,transparent)]',
  neutral: 'border-[var(--border)] text-[var(--text-muted)]',
};

function StatusBadge({ value }: { value: string }) {
  const tone = BADGE_TONES[value.trim().toLowerCase()] ?? 'neutral';
  return (
    <span
      className={`inline-flex items-center border px-2 py-0.5 text-xs font-semibold ${BADGE_CLASSES[tone]}`}
    >
      {value}
    </span>
  );
}

/**
 * Shared shell for every Administration settings screen: a one-paragraph
 * explanation, an optional KPI row, and the settings table.
 *
 * Column definitions arrive from the server route as plain objects — no
 * `renderCell` functions, which would not survive the server/client boundary.
 * `statusColumns` is how a route asks for badge rendering instead.
 */
export function AdminSettingsPage({
  description,
  kpis = [],
  columns,
  records,
  statusColumns = [],
  emptyMessage = 'No configuration yet.',
  exportFileName,
  defaultPageSize = 20,
}: AdminSettingsPageProps) {
  const decoratedColumns = useMemo<DataTableColumn[]>(() => {
    if (statusColumns.length === 0) return columns;
    const badged = new Set(statusColumns);
    return columns.map((column) =>
      badged.has(column.key)
        ? {
            ...column,
            renderValue: (value: unknown) =>
              typeof value === 'string' && value.trim() !== '' ? (
                <StatusBadge value={value} />
              ) : (
                '—'
              ),
          }
        : column,
    );
  }, [columns, statusColumns]);

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-3xl text-sm leading-relaxed text-[var(--text-muted)]">
        {description}
      </p>

      {kpis.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map((kpi) => (
            <KpiCard
              key={kpi.label}
              label={kpi.label}
              value={kpi.value}
              valueStyle={kpi.valueStyle}
              currency={kpi.currency}
              maximumFractionDigits={kpi.maximumFractionDigits}
              subtitle={kpi.subtitle}
              tone={kpi.tone}
              displayValue={kpi.displayValue}
            />
          ))}
        </div>
      ) : null}

      <DataTable
        records={records}
        columns={decoratedColumns}
        emptyMessage={emptyMessage}
        exportable
        exportFileName={exportFileName}
        globalSearch
        paginate
        defaultPageSize={defaultPageSize}
      />
    </div>
  );
}
