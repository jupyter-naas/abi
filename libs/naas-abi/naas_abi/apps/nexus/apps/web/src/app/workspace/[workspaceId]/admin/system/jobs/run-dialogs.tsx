'use client';

/** Starting a run (with an optional payload) and cancelling one. */
import { useState } from 'react';
import { AlertTriangle, Play, Square } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { Kbd, Notice } from '../data/data-ui';
import { Modal } from '../data/modal';
import { CodeView } from '../data/viewers/code-view';
import type { RunSummary } from './jobs-types';

/** The payload must be a JSON object; an error message, or ``null``. */
export function payloadError(text: string): string | null {
  if (!text.trim()) return null;
  try {
    const value = JSON.parse(text) as unknown;
    return value !== null && typeof value === 'object' && !Array.isArray(value) ? null : 'The payload must be a JSON object.';
  } catch {
    return 'Not valid JSON.';
  }
}

export function TriggerDialog({
  job,
  moduleId,
  initialPayload,
  rerun,
  onSubmit,
  onClose,
}: {
  job: string;
  moduleId: string;
  initialPayload: unknown;
  rerun: boolean;
  onSubmit: (payload: Record<string, unknown>) => Promise<Failure | null>;
  onClose: () => void;
}) {
  const [text, setText] = useState(() =>
    initialPayload && typeof initialPayload === 'object' && Object.keys(initialPayload as object).length
      ? JSON.stringify(initialPayload, null, 2)
      : '{}',
  );
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const error = payloadError(text);
  const submit = async () => {
    if (error || busy) return;
    setBusy(true);
    const result = await onSubmit(text.trim() ? (JSON.parse(text) as Record<string, unknown>) : {});
    setBusy(false);
    if (result) setFailure(result);
  };
  return (
    <Modal
      title={rerun ? `Run ${job} again` : `Run ${job} now`}
      subtitle={<span className="data-mono">{moduleId}</span>}
      icon={<Play size={18} />}
      size="lg"
      onClose={onClose}
      onSubmit={submit}
      footer={
        <>
          <span className="data-modal-hint">
            Recorded in the audit log · <Kbd>⌘</Kbd>
            <Kbd>↵</Kbd>
          </span>
          <button type="button" className="data-button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="data-button data-button-primary" disabled={Boolean(error) || busy} onClick={submit}>
            <Play size={14} aria-hidden="true" /> {busy ? 'Starting…' : 'Run'}
          </button>
        </>
      }
    >
      <p className="data-modal-text">
        Publishes one trigger for this job. A host picks it up like a schedule tick; it counts against the job&apos;s
        concurrency and retries like any run. The payload reaches the handler as <code className="data-mono">ctx.payload</code>.
      </p>
      <div className="jobs-payload-editor">
        <CodeView value={text} language="json" readOnly={false} onChange={setText} />
      </div>
      {error && <p className="data-field-error">{error}</p>}
      {failure && (
        <Notice tone="danger">
          <AlertTriangle size={14} aria-hidden="true" /> {failure.reason}
        </Notice>
      )}
    </Modal>
  );
}

export function CancelDialog({
  run,
  onConfirm,
  onClose,
}: {
  run: RunSummary;
  onConfirm: () => Promise<Failure | null>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const submit = async () => {
    setBusy(true);
    const result = await onConfirm();
    setBusy(false);
    if (result) setFailure(result);
  };
  return (
    <Modal
      title={`Cancel ${run.job}?`}
      subtitle={<span className="data-mono">{run.run_id}</span>}
      icon={<Square size={18} />}
      tone="danger"
      onClose={onClose}
      onSubmit={submit}
      footer={
        <>
          <span className="data-modal-hint">Recorded in the audit log</span>
          <button type="button" className="data-button" onClick={onClose}>
            Keep running
          </button>
          <button type="button" className="data-button data-button-danger" disabled={busy} onClick={submit}>
            {busy ? 'Cancelling…' : 'Cancel run'}
          </button>
        </>
      }
    >
      <p className="data-modal-text">
        Cancelling is cooperative: the host sets <code className="data-mono">ctx.cancelled</code> and the job stops at
        its next check. Sync jobs are interrupted after the grace period; work already done is not rolled back.
      </p>
      {failure && (
        <Notice tone="danger">
          <AlertTriangle size={14} aria-hidden="true" /> {failure.reason}
        </Notice>
      )}
    </Modal>
  );
}
