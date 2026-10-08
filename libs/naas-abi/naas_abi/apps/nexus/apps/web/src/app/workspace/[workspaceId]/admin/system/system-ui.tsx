'use client';

import type { ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { unavailableSources, type Tone } from './system-model';
import type { JobSummary, SourceStatus } from './system-types';

export function StatusDot({ tone }: { tone: Tone }) {
  return <span className={`system-status-dot system-status-dot-${tone}`} aria-hidden="true" />;
}

export function Status({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className="system-status">
      <StatusDot tone={tone} />
      {label}
    </span>
  );
}

export function SourceNote({ label, reason }: { label: string; reason: string }) {
  return (
    <p className="system-source-note" role="status">
      <strong>{label} unavailable.</strong> {reason}
    </p>
  );
}

/** One note per source the API could not reach, with its reason. */
export function SourceNotes({ sources }: { sources: Record<string, SourceStatus> }) {
  const missing = unavailableSources(sources);
  if (!missing.length) return null;
  return (
    <div className="system-source-notes">
      {missing.map((s) => (
        <SourceNote key={s.source} label={s.label} reason={s.reason} />
      ))}
    </div>
  );
}

export function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="system-section">
      <header className="system-section-header">
        <h2 className="system-section-title">{title}</h2>
        {subtitle && <p className="system-section-subtitle">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

export function Kpi({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="system-kpi">
      <span className="system-kpi-label">{label}</span>
      <span className="system-kpi-value">{value}</span>
      {hint !== undefined && <span className="system-kpi-hint">{hint}</span>}
    </div>
  );
}

export function RowToggle({
  open,
  disabled,
  onToggle,
  children,
}: {
  open: boolean;
  disabled?: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className="system-row-toggle"
      aria-expanded={open}
      disabled={disabled}
      onClick={onToggle}
    >
      <span className="system-row-toggle-icon" aria-hidden="true">
        {disabled ? null : open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </span>
      <span className="system-mono">{children}</span>
    </button>
  );
}

export function Chips({ values, muted }: { values: string[]; muted?: boolean }) {
  if (!values.length) return <span className="system-empty-cell">–</span>;
  return (
    <span className="system-chips">
      {values.map((v) => (
        <span key={v} className={muted ? 'system-chip system-chip-muted' : 'system-chip'}>
          {v}
        </span>
      ))}
    </span>
  );
}

export function JobList({ jobs }: { jobs: JobSummary[] }) {
  if (!jobs.length) return <span className="system-empty-cell">–</span>;
  return (
    <ul className="system-jobs">
      {jobs.map((job) => (
        <li key={job.name} className="system-job" title={job.description || undefined}>
          <span className="system-job-name">{job.name}</span>
          <Chips values={job.triggers.length ? job.triggers : ['manual']} muted />
        </li>
      ))}
    </ul>
  );
}

export function toggled(set: Set<string>, key: string): Set<string> {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}
