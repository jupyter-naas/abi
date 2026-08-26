type ProgressBarProps = {
  label: string;
  current: number;
  target: number;
  status?: string;
};

export function ProgressBar({ label, current, target, status }: ProgressBarProps) {
  const pct = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;

  return (
    <div>
      <div className="flex items-end justify-between mb-1">
        <div>
          <span className="text-sm font-semibold">{label}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-base font-bold">{pct}%</span>
          {status ? (
            <span className="text-xs px-2 py-0.5 rounded-full font-semibold badge-info">
              {status}
            </span>
          ) : null}
        </div>
      </div>
      <div className="progress-bar-bg h-4 relative rounded-md">
        <div
          className="progress-bar-fill rounded-md h-full"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-xs mt-2 text-[var(--text-muted)]">
        {new Intl.NumberFormat('fr-FR').format(current)} € /{' '}
        {new Intl.NumberFormat('fr-FR').format(target)} €
      </div>
    </div>
  );
}
