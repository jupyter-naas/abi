'use client';

/** Destructive confirmation and the value editor (create or replace). */
import { useState } from 'react';
import { AlertTriangle, Eye, EyeOff, FileUp, Pencil, Plus, Trash2, UploadCloud } from 'lucide-react';
import type { Failure, Result, WriteOptions } from './data-api';
import { TTL_UNITS, childId, confirmed, formatBytes, ttlSeconds, type TtlUnit } from './data-model';
import type { ResourceEntry } from './data-types';
import { CopyButton, Kbd, Notice } from './data-ui';
import { Modal } from './modal';
import type { ServiceView } from './services/types';
import { CodeView } from './viewers/code-view';

function ErrorLine({ failure }: { failure: Failure | null }) {
  if (!failure) return null;
  return (
    <Notice tone="danger">
      <AlertTriangle size={14} aria-hidden="true" /> {failure.reason}
    </Notice>
  );
}

function ConfirmInput({
  id,
  verb,
  value,
  onChange,
}: {
  id: string;
  verb: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="data-confirm">
      <span className="data-confirm-label">
        Type <code className="data-mono">{id}</code> to {verb}
      </span>
      <input
        className={`data-input${value && !confirmed(value, id) ? ' data-input-invalid' : ''}`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
        aria-label="Type the id to confirm"
        data-autofocus
      />
    </label>
  );
}

export function DeleteDialog({
  entry,
  noun,
  verb = 'Delete',
  warning,
  onConfirm,
  onClose,
}: {
  entry: ResourceEntry;
  noun: string;
  verb?: string;
  warning?: string;
  onConfirm: (typed: string) => Promise<Failure | null>;
  onClose: () => void;
}) {
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const ready = confirmed(typed, entry.id) && !busy;
  const submit = async () => {
    if (!ready) return;
    setBusy(true);
    const result = await onConfirm(typed);
    setBusy(false);
    if (result) setFailure(result);
  };
  return (
    <Modal
      title={`${verb} ${noun}`}
      subtitle={entry.name}
      icon={<Trash2 size={18} />}
      tone="danger"
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
          <button type="button" className="data-button data-button-danger" disabled={!ready} onClick={submit}>
            {busy ? `${verb === 'Delete' ? 'Deleting' : `${verb}ing`}…` : `${verb} ${noun}`}
          </button>
        </>
      }
    >
      <p className="data-modal-text">{warning ? `${warning} This cannot be undone.` : 'This cannot be undone.'}</p>
      <div className="data-id-box">
        <code className="data-mono">{entry.id}</code>
        <CopyButton value={entry.id} label="Copy id" />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <ConfirmInput id={entry.id} verb={`${verb.toLowerCase()} it`} value={typed} onChange={setTyped} />
      </form>
      <ErrorLine failure={failure} />
    </Modal>
  );
}

export interface EditorRequest {
  mode: 'create' | 'edit';
  parent: string;
  parentLabel: string;
  entry?: ResourceEntry;
  initial: string;
}

export function EditorDialog({
  request,
  view,
  writeFormat,
  expiry = false,
  onSave,
  onClose,
}: {
  request: EditorRequest;
  view: ServiceView;
  writeFormat: string;
  /** The service takes an expiry on create (``capabilities.expiry``). */
  expiry?: boolean;
  onSave: (
    id: string,
    body: Blob | string,
    confirm?: string,
    options?: WriteOptions,
  ) => Promise<Result<ResourceEntry>>;
  onClose: () => void;
}) {
  const editing = request.mode === 'edit';
  const spec = view.editor ?? { language: () => 'plaintext' };
  const [name, setName] = useState('');
  const [text, setText] = useState(request.initial);
  const [file, setFile] = useState<File | null>(null);
  const [tab, setTab] = useState<'write' | 'upload'>('write');
  const [typed, setTyped] = useState('');
  const [mustConfirm, setMustConfirm] = useState<string | null>(editing ? (request.entry?.id ?? null) : null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [shown, setShown] = useState(!spec.secret);
  const [ttlAmount, setTtlAmount] = useState('');
  const [ttlUnit, setTtlUnit] = useState<TtlUnit>('minutes');
  const compact = typeof spec.compact === 'function' ? spec.compact(request.entry) : Boolean(spec.compact);

  const id = editing ? (request.entry?.id ?? '') : childId(request.parent, name || (file?.name ?? ''));
  const language = spec.language(id || name, request.entry);
  const nameError = !editing && name ? (spec.validateName?.(name) ?? null) : null;
  const valueError = tab === 'write' && text ? (spec.validate?.(text) ?? null) : null;
  const hasName = editing || Boolean(name.trim() || (tab === 'upload' && file));
  const asksExpiry = expiry && !editing;
  const ttl = asksExpiry ? ttlSeconds(ttlAmount, ttlUnit) : undefined;
  const ready =
    hasName &&
    !nameError &&
    !valueError &&
    ttl !== null &&
    !busy &&
    (tab === 'write' || file !== null) &&
    (mustConfirm === null || confirmed(typed, mustConfirm));

  const save = async () => {
    if (!ready) return;
    setBusy(true);
    setFailure(null);
    const body: Blob | string = tab === 'upload' && file ? file : text;
    const options = asksExpiry ? (ttl ? { ttlSeconds: ttl } : {}) : undefined;
    const result = await onSave(id, body, mustConfirm ? typed : undefined, options);
    setBusy(false);
    if (result.ok) return;
    if (result.status === 409 && result.confirm) {
      setMustConfirm(result.confirm);
      setTyped('');
      setFailure({ ...result, reason: `${result.confirm} already exists. Type its id to replace it.` });
      return;
    }
    setFailure(result);
  };

  const title = editing ? `Edit ${request.entry?.name ?? ''}` : `New ${view.noun.one}`;
  return (
    <Modal
      title={title}
      subtitle={
        editing ? (
          <code className="data-mono">{request.entry?.id}</code>
        ) : request.parent ? (
          <>in {request.parentLabel}</>
        ) : (
          view.label
        )
      }
      icon={editing ? <Pencil size={18} /> : <Plus size={18} />}
      size={compact ? 'md' : 'xl'}
      onClose={onClose}
      onSubmit={save}
      footer={
        <>
          <span className="data-modal-hint">
            {writeFormat ? <>Format: {writeFormat}</> : <>Saved as text</>} · <Kbd>⌘</Kbd>
            <Kbd>S</Kbd> to save
          </span>
          <button type="button" className="data-button" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="data-button data-button-primary" disabled={!ready} onClick={save}>
            {busy ? 'Saving…' : mustConfirm ? 'Replace' : editing ? 'Save' : 'Create'}
          </button>
        </>
      }
    >
      {!editing && (
        <label className="data-editor-name">
          <span className="data-editor-name-prefix">
            {request.parent ? `${request.parentLabel} /` : 'Name'}
          </span>
          <input
            className={`data-input${nameError ? ' data-input-invalid' : ''}`}
            value={name}
            placeholder={spec.namePlaceholder ?? `${view.noun.one} name`}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            aria-label="Name"
            data-autofocus
          />
        </label>
      )}
      {nameError && <p className="data-field-error">{nameError}</p>}
      {spec.allowUpload && (
        <div className="data-segmented" role="tablist" aria-label="Value source">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'write'}
            className={tab === 'write' ? 'data-segment data-segment-active' : 'data-segment'}
            onClick={() => setTab('write')}
          >
            <Pencil size={13} aria-hidden="true" /> Write
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'upload'}
            className={tab === 'upload' ? 'data-segment data-segment-active' : 'data-segment'}
            onClick={() => setTab('upload')}
          >
            <FileUp size={13} aria-hidden="true" /> Upload a file
          </button>
        </div>
      )}
      {tab === 'write' && compact ? (
        <label className="data-editor-value">
          <span className="data-confirm-label">Value</span>
          <span className="data-editor-value-row">
            <textarea
              className={`data-input data-editor-textarea${shown ? '' : ' data-editor-textarea-hidden'}`}
              value={text}
              rows={3}
              onChange={(e) => setText(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-label="Value"
              data-autofocus={editing ? true : undefined}
            />
            {spec.secret && (
              <button
                type="button"
                className="data-icon-button data-icon-button-bordered"
                aria-label={shown ? 'Hide value' : 'Show value'}
                title={shown ? 'Hide value' : 'Show value'}
                onClick={() => setShown(!shown)}
              >
                {shown ? <EyeOff size={14} aria-hidden="true" /> : <Eye size={14} aria-hidden="true" />}
              </button>
            )}
          </span>
        </label>
      ) : tab === 'write' ? (
        <div className="data-editor-code">
          <CodeView value={text} language={language} readOnly={false} onChange={setText} />
        </div>
      ) : (
        <label className="data-dropzone">
          <UploadCloud size={22} aria-hidden="true" />
          <span>{file ? `${file.name} · ${formatBytes(file.size)}` : 'Choose a file to upload'}</span>
          <input
            type="file"
            className="data-visually-hidden"
            aria-label="File to upload"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
      )}
      {valueError && <p className="data-field-error">{valueError}</p>}
      {asksExpiry && (
        <div className="data-editor-expiry">
          <label className="data-confirm-label" htmlFor="data-editor-expiry">
            Expires after
          </label>
          <input
            id="data-editor-expiry"
            className={`data-input${ttl === null ? ' data-input-invalid' : ''}`}
            value={ttlAmount}
            placeholder="never"
            inputMode="numeric"
            onChange={(e) => setTtlAmount(e.target.value)}
            aria-label="Expires after"
          />
          <select
            className="data-input"
            value={ttlUnit}
            onChange={(e) => setTtlUnit(e.target.value as TtlUnit)}
            aria-label="Expiry unit"
          >
            {Object.keys(TTL_UNITS).map((unit) => (
              <option key={unit} value={unit}>
                {unit}
              </option>
            ))}
          </select>
        </div>
      )}
      {ttl === null && <p className="data-field-error">The expiry must be a whole number above zero.</p>}
      {mustConfirm && (
        <ConfirmInput id={mustConfirm} verb="replace its value" value={typed} onChange={setTyped} />
      )}
      <ErrorLine failure={failure} />
    </Modal>
  );
}

/** A service's own creation form (a composer, an uploader) in the same frame. */
export function CreateDialog({
  view,
  parent,
  parentLabel,
  onSave,
  onClose,
}: {
  view: ServiceView;
  parent: string;
  parentLabel: string;
  onSave: (id: string, body: Blob | string) => Promise<Result<ResourceEntry>>;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const submit = async (id: string, body: Blob | string) => {
    setBusy(true);
    setFailure(null);
    const result = await onSave(id, body);
    setBusy(false);
    if (!result.ok) setFailure(result);
    return result.ok;
  };
  return (
    <Modal
      title={view.createLabel ?? `New ${view.noun.one}`}
      subtitle={parent ? <>in {parentLabel}</> : view.label}
      icon={<Plus size={18} />}
      size="lg"
      onClose={onClose}
    >
      {view.create?.({ parent, busy, submit, close: onClose })}
      <ErrorLine failure={failure} />
    </Modal>
  );
}
