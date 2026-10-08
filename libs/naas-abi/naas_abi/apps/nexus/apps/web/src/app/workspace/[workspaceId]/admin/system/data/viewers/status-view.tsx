'use client';

/** Something with a lifecycle (an environment, an instance): its phase, then its facts. */
import { StatusPill, type Tone } from '../data-ui';

export function phaseTone(phase: string | undefined): Tone {
  const p = (phase ?? '').toLowerCase();
  if (/(running|ready|ok|healthy|active|serving|succeeded)/.test(p)) return 'success';
  if (/(start|pending|provision|creating|queued|deploy|registering)/.test(p)) return 'info';
  if (/(fail|error|unhealthy|crash|expired)/.test(p)) return 'danger';
  if (/(stop|paused|deleting|draining|degraded)/.test(p)) return 'warn';
  return 'neutral';
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function StatusView({ phase, fields }: { phase?: string; fields?: Record<string, unknown> }) {
  return (
    <div className="status">
      {phase && (
        <div className="status-phase">
          <StatusPill tone={phaseTone(phase)} label={phase} pulse={phaseTone(phase) === 'info'} />
        </div>
      )}
      <dl className="status-fields">
        {Object.entries(fields ?? {}).map(([label, value]) => (
          <div key={label} className="status-field">
            <dt>{label}</dt>
            <dd title={show(value)}>{show(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
