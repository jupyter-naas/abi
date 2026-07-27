'use client';

import { ThemeNumber } from '@/components/theme/ThemeNumber';
import type { CashBridgeStep } from '@/lib/data/treasury';

const CHART_HEIGHT_REM = 17;

const KIND_COLOR: Record<CashBridgeStep['kind'], string> = {
  anchor: 'var(--primary)',
  inflow: 'var(--recovery-success)',
  outflow: 'var(--recovery-danger)',
};

function stepBounds(step: CashBridgeStep): { low: number; high: number } {
  if (step.kind === 'anchor') {
    return { low: Math.min(0, step.balance), high: Math.max(0, step.balance) };
  }
  const before = step.balance - step.value;
  return { low: Math.min(before, step.balance), high: Math.max(before, step.balance) };
}

export function CashBridgeChart({
  steps,
  onStepClick,
  activeStepKey,
}: {
  steps: CashBridgeStep[];
  /** Called when a clickable (typed) step is activated. */
  onStepClick?: (step: CashBridgeStep) => void;
  activeStepKey?: string | null;
}) {
  const bounds = steps.map(stepBounds);
  const domainMax = Math.max(0, ...bounds.map((b) => b.high));
  const domainMin = Math.min(0, ...bounds.map((b) => b.low));
  const span = domainMax - domainMin || 1;

  const toPct = (value: number) => ((value - domainMin) / span) * 100;
  const zeroPct = toPct(0);

  return (
    <div className="glass rounded-lg p-6">
      <div className="overflow-x-auto">
        <div className="min-w-[34rem]">
          <div
            className="relative flex items-stretch gap-3 sm:gap-5"
            style={{ height: `${CHART_HEIGHT_REM}rem` }}
          >
            <div
              className="pointer-events-none absolute inset-x-0 border-t border-dashed border-[var(--border)]"
              style={{ bottom: `${zeroPct}%` }}
              aria-hidden
            />

            {steps.map((step, index) => {
              const b = bounds[index];
              const bottomPct = toPct(b.low);
              const heightPct = Math.max(
                ((b.high - b.low) / span) * 100,
                b.high === b.low ? 0 : 1.5,
              );
              const color = KIND_COLOR[step.kind];
              const labelAbove = bottomPct + heightPct <= 82;
              const clickable = Boolean(step.type) && Boolean(onStepClick);
              const active = activeStepKey === step.key;
              const Tag = clickable ? 'button' : 'div';
              return (
                <Tag
                  key={step.key}
                  type={clickable ? 'button' : undefined}
                  onClick={clickable ? () => onStepClick?.(step) : undefined}
                  className={`relative flex min-w-0 flex-1 flex-col rounded-sm text-left outline-none${
                    clickable
                      ? ' cursor-pointer transition-colors hover:bg-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--secondary)]'
                      : ''
                  }${active ? ' bg-[var(--accent)]' : ''}`}
                  title={
                    clickable
                      ? `${step.label} — cliquer pour détailler et filtrer le tableau`
                      : `${step.label} — solde ${step.balance.toLocaleString('fr-FR')} €`
                  }
                >
                  <div className="relative flex-1">
                    <div
                      className="absolute inset-x-[12%] rounded-sm transition-[height,bottom] duration-500"
                      style={{
                        bottom: `${bottomPct}%`,
                        height: `${heightPct}%`,
                        backgroundColor: color,
                        opacity: step.kind === 'anchor' ? 1 : 0.9,
                      }}
                    />
                    <div
                      className="absolute inset-x-0 flex justify-center"
                      style={
                        labelAbove
                          ? { bottom: `calc(${bottomPct + heightPct}% + 4px)` }
                          : { bottom: `calc(${bottomPct}% - 20px)` }
                      }
                    >
                      <ThemeNumber
                        value={step.value}
                        style="currency"
                        maximumFractionDigits={0}
                        className="whitespace-nowrap text-xs font-semibold tabular-nums"
                      />
                    </div>
                  </div>
                </Tag>
              );
            })}
          </div>

          <div className="mt-3 flex items-start gap-3 border-t border-[var(--border)] pt-3 sm:gap-5">
            {steps.map((step) => (
              <div
                key={step.key}
                className="min-w-0 flex-1 text-center text-xs text-[var(--text-muted)]"
              >
                <span
                  className={
                    step.kind === 'anchor' ? 'font-semibold text-[var(--text)]' : undefined
                  }
                  title={step.label}
                >
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-[var(--text-muted)]">
        <LegendSwatch color="var(--primary)" label="Solde (position / prévisionnel)" />
        <LegendSwatch color="var(--recovery-success)" label="Encaissement" />
        <LegendSwatch color="var(--recovery-danger)" label="Décaissement" />
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-3 w-3 rounded-sm"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      {label}
    </span>
  );
}
