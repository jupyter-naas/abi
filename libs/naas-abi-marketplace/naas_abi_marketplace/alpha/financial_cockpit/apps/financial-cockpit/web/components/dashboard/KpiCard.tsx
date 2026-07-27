'use client';

import { ThemeNumber } from '@/components/theme/ThemeNumber';
import type {
  FormatThemeNumberOptions,
  NumberDisplayStyle,
  PercentInput,
} from '@/lib/theme/typography';
import { numberClassName } from '@/lib/theme/typography';

type KpiCardTone = 'default' | 'success' | 'warning' | 'orange' | 'danger';

type KpiCardProps = {
  label: string;
  value: number;
  /** @deprecated Prefer `valueStyle="currency"` and `currency`. */
  unit?: string;
  valueStyle?: NumberDisplayStyle;
  currency?: string;
  percentInput?: PercentInput;
  maximumFractionDigits?: number;
  subtitle?: string;
  trend?: number;
  tone?: KpiCardTone;
  hint?: string;
  onAction?: () => void;
  actionLabel?: string;
};

const toneValueClass: Record<KpiCardTone, string> = {
  default: '',
  success: 'kpi-value--success',
  warning: 'kpi-value--warning',
  orange: 'kpi-value--orange',
  danger: 'kpi-value--danger',
};

function buildFormatOptions({
  valueStyle,
  currency,
  unit,
  percentInput,
  maximumFractionDigits,
}: Pick<
  KpiCardProps,
  'valueStyle' | 'currency' | 'unit' | 'percentInput' | 'maximumFractionDigits'
>): FormatThemeNumberOptions {
  if (valueStyle) {
    return {
      style: valueStyle,
      currency,
      percentInput,
      maximumFractionDigits,
    };
  }

  if (unit === '%') {
    return {
      style: 'percent',
      percentInput: percentInput ?? 'percent',
      maximumFractionDigits,
    };
  }

  if (unit === '€') {
    return {
      style: 'currency',
      currency: currency ?? 'EUR',
      maximumFractionDigits,
    };
  }

  return {
    style: 'decimal',
    unit,
    maximumFractionDigits,
  };
}

export function KpiCard({
  label,
  value,
  unit,
  valueStyle,
  currency,
  percentInput,
  maximumFractionDigits,
  subtitle,
  trend,
  tone = 'default',
  hint,
  onAction,
  actionLabel,
}: KpiCardProps) {
  const formatOptions = buildFormatOptions({
    valueStyle,
    currency,
    unit,
    percentInput,
    maximumFractionDigits,
  });
  const resolvedStyle = formatOptions.style ?? 'decimal';
  const valueClassName =
    `${numberClassName(resolvedStyle)} ${toneValueClass[tone]}`.trim();

  return (
    <div className={`kpi-card card-hover relative${onAction ? ' pr-11' : ''}`}>
      {onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center text-[#e4e4e7] transition-colors hover:text-[var(--secondary)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
          aria-label={actionLabel ?? `Voir le détail — ${label}`}
          title={actionLabel ?? `Voir le détail — ${label}`}
        >
          <ChevronCircleIcon />
        </button>
      ) : null}
      <p
        className={`type-title-5 mb-2${hint ? ' cursor-help' : ''}`}
        title={hint}
      >
        {label}
      </p>
      <ThemeNumber value={value} {...formatOptions} className={valueClassName} />
      {subtitle ? <p className="type-subtitle mt-2 text-sm">{subtitle}</p> : null}
      {trend !== undefined ? (
        <p
          className={`text-xs mt-1 font-semibold ${
            trend >= 0 ? 'text-emerald-500' : 'text-red-500'
          }`}
        >
          {trend >= 0 ? '+' : ''}
          <ThemeNumber
            value={trend}
            style="percent"
            percentInput="percent"
            className="inline type-number text-xs"
          />
        </p>
      ) : null}
    </div>
  );
}

function ChevronCircleIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M8.25 7.5 11.25 10 8.25 12.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
