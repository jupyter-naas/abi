'use client';

/** Starting a run (with an optional payload) and cancelling one. */
import { useMemo, useState } from 'react';
import { AlertTriangle, Play, Square } from 'lucide-react';
import type { Failure } from '../data/data-api';
import { Kbd, Notice } from '../data/data-ui';
import { Modal } from '../data/modal';
import { CodeView } from '../data/viewers/code-view';
import type { JsonSchema, RunSummary } from './jobs-types';
import { SchemaForm } from './schema-fields';
import {
  buildForm,
  formIssues,
  initialValues,
  toPayload,
  validate,
  type FormState,
  type Issue,
} from './schema-form';

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

const parseObject = (text: string): Record<string, unknown> => (text.trim() ? (JSON.parse(text) as Record<string, unknown>) : {});

const pretty = (value: unknown) =>
  value && typeof value === 'object' && Object.keys(value as object).length ? JSON.stringify(value, null, 2) : '{}';

/** A pointer as the field it names: "/window/days" is "window.days"; "" is the input itself. */
const where = (path: string) => (path ? path.slice(1).split('/').join('.') : 'input');

function IssueList({ issues }: { issues: Issue[] }) {
  return (
    <ul className="sf-issues" aria-label="Problems with the input">
      {issues.map((issue, i) => (
        <li key={i} className="data-field-error">
          <code className="data-mono">{where(issue.path)}</code> {issue.message}
        </li>
      ))}
    </ul>
  );
}

/**
 * Start a run. A workflow brings its input schema: the dialog renders a form
 * from it (JSON editor on the side), or only the editor when the schema has no
 * form. The input is checked against the schema before anything is sent, and
 * the API's own refusal (422) is shown too.
 */
export function TriggerDialog({
  job,
  moduleId,
  initialPayload,
  rerun,
  schema = null,
  workflow = false,
  onSubmit,
  onClose,
}: {
  job: string;
  moduleId: string;
  initialPayload: unknown;
  rerun: boolean;
  /** The workflow's input schema; null for a plain job or a workflow that declares none. */
  schema?: JsonSchema | null;
  workflow?: boolean;
  onSubmit: (payload: Record<string, unknown>) => Promise<Failure | null>;
  onClose: () => void;
}) {
  const fields = useMemo(() => buildForm(schema), [schema]);
  const [mode, setMode] = useState<'form' | 'json'>(fields ? 'form' : 'json');
  const [form, setForm] = useState<FormState>(() => ({ values: initialValues(fields ?? [], initialPayload), drafts: {} }));
  const [text, setText] = useState(() => pretty(initialPayload));
  const [busy, setBusy] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);

  const syntax = mode === 'json' ? payloadError(text) : null;
  const issues: Issue[] = useMemo(() => {
    if (!schema) return [];
    if (mode === 'form' && fields) return formIssues(schema, fields, form);
    return syntax ? [] : validate(schema, parseObject(text));
  }, [schema, fields, mode, form, text, syntax]);

  const switchTo = (next: 'form' | 'json') => {
    if (next === mode || !fields) return;
    setSwitchError(null);
    if (next === 'json') {
      setText(pretty(toPayload(fields, form.values)));
    } else {
      const error = payloadError(text);
      if (error) return setSwitchError(`${error} Fix the JSON before going back to the form.`);
      setForm({ values: initialValues(fields, parseObject(text)), drafts: {} });
    }
    setMode(next);
  };

  const submit = async () => {
    if (syntax || busy) return;
    if (issues.length) {
      setAttempted(true);
      return;
    }
    setBusy(true);
    setFailure(null);
    const payload = mode === 'form' && fields ? toPayload(fields, form.values) : parseObject(text);
    const result = await onSubmit(payload);
    setBusy(false);
    if (result) {
      setFailure(result);
      setAttempted(true);
    }
  };

  // What the API refused (cleared as soon as the input changes).
  const refused = failure?.errors?.length ? failure.errors : [];
  const shown = attempted ? (refused.length && !issues.length ? refused : issues) : [];
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
          <button type="button" className="data-button data-button-primary" disabled={Boolean(syntax) || busy} onClick={submit}>
            <Play size={14} aria-hidden="true" /> {busy ? 'Starting…' : 'Run'}
          </button>
        </>
      }
    >
      {workflow ? (
        <p className="data-modal-text">
          Starts a durable run of this workflow. The input is checked against its input schema first; if a host stops
          mid-run, the retry resumes after the steps that finished.
        </p>
      ) : (
        <p className="data-modal-text">
          Publishes one trigger for this job. A host picks it up like a schedule tick; it counts against the job&apos;s
          concurrency and retries like any run. The payload reaches the handler as <code className="data-mono">ctx.payload</code>.
        </p>
      )}
      {fields && (
        <div className="data-segmented" role="tablist" aria-label="Input editor">
          {(['form', 'json'] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={mode === m ? 'data-segment data-segment-active' : 'data-segment'}
              onClick={() => switchTo(m)}
            >
              {m === 'form' ? 'Form' : 'JSON'}
            </button>
          ))}
        </div>
      )}
      {schema && !fields && (
        <Notice tone="neutral">
          <span>This input schema has no generated form (it uses shapes a form cannot show). Edit the JSON: it is checked against the schema before it is sent.</span>
        </Notice>
      )}
      {mode === 'form' && fields ? (
        <SchemaForm fields={fields} state={form} issues={shown} onState={(next) => {
            setForm(next);
            setFailure(null);
          }} />
      ) : (
        <div className="jobs-payload-editor">
          <CodeView
            value={text}
            language="json"
            readOnly={false}
            onChange={(next) => {
              setText(next);
              setFailure(null);
            }}
          />
        </div>
      )}
      {switchError && <p className="data-field-error">{switchError}</p>}
      {syntax && <p className="data-field-error">{syntax}</p>}
      {mode === 'json' && shown.length > 0 && <IssueList issues={shown} />}
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
