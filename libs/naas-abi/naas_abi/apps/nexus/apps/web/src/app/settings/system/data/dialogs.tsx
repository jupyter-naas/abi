'use client';

/** Destructive confirmation and the value editor (create or replace), on the kit's dialog. */
import { useState, type KeyboardEvent } from 'react';
import { AlertTriangle, Eye, EyeOff, FileUp, Pencil, Plus, Trash2, UploadCloud } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input, Select, Textarea } from '@/components/ui/input';
import { Notice } from '@/components/ui/notice';
import { Spinner } from '@/components/ui/spinner';
import { Tabs } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import type { Failure, Result, WriteOptions } from './data-api';
import { TTL_UNITS, childId, confirmed, formatBytes, ttlSeconds, type TtlUnit } from './data-model';
import type { ResourceEntry } from './data-types';
import { CopyButton, Kbd } from './data-ui';
import type { ServiceView } from './services/types';
import { CodeView } from './viewers/code-view';

function ErrorLine({ failure }: { failure: Failure | null }) {
  if (!failure) return null;
  return (
    <Notice tone="error" icon={<AlertTriangle size={14} aria-hidden="true" />}>
      {failure.reason}
    </Notice>
  );
}

const invalid = (bad: boolean) => (bad ? { 'aria-invalid': true, className: 'border-destructive' } : {});

function ConfirmInput({ id, verb, value, onChange }: { id: string; verb: string; value: string; onChange: (value: string) => void }) {
  return (
    <Field label={<>Type <code className="font-mono">{id}</code> to {verb}</>}>
      <Input
        {...invalid(Boolean(value) && !confirmed(value, id))}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
        aria-label="Type the id to confirm"
        data-autofocus
      />
    </Field>
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
    <Dialog
      title={`${verb} ${noun}`}
      description={entry.name}
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
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={!ready} onClick={submit}>
            {busy ? <Spinner size={14} /> : null}
            {busy ? `${verb === 'Delete' ? 'Deleting' : `${verb}ing`}…` : `${verb} ${noun}`}
          </Button>
        </>
      }
    >
      <p className="text-muted-foreground">{warning ? `${warning} This cannot be undone.` : 'This cannot be undone.'}</p>
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
    </Dialog>
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
  // ⌘/Ctrl+S saves too (the kit dialog submits on ⌘/Ctrl+Enter).
  const saveKey = (event: KeyboardEvent) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 's') {
      event.preventDefault();
      void save();
    }
  };

  const title = editing ? `Edit ${request.entry?.name ?? ''}` : `New ${view.noun.one}`;
  return (
    <Dialog
      title={title}
      description={
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
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!ready} onClick={save}>
            {busy ? <Spinner size={14} /> : null}
            {busy ? 'Saving…' : mustConfirm ? 'Replace' : editing ? 'Save' : 'Create'}
          </Button>
        </>
      }
    >
      <div className="space-y-3" onKeyDown={saveKey}>
        {!editing && (
          <label className="data-editor-name">
            <span className="data-editor-name-prefix">{request.parent ? `${request.parentLabel} /` : 'Name'}</span>
            <Input
              {...invalid(Boolean(nameError))}
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
          <Tabs
            variant="segmented"
            label="Value source"
            className="w-fit"
            value={tab}
            onChange={setTab}
            items={[
              { id: 'write', label: 'Write', icon: <Pencil size={13} aria-hidden="true" /> },
              { id: 'upload', label: 'Upload a file', icon: <FileUp size={13} aria-hidden="true" /> },
            ]}
          />
        )}
        {tab === 'write' && compact ? (
          <Field label="Value">
            <span className="data-editor-value-row">
              <Textarea
                className={cn('data-editor-textarea', !shown && 'data-editor-textarea-hidden')}
                value={text}
                rows={3}
                onChange={(e) => setText(e.target.value)}
                autoComplete="off"
                spellCheck={false}
                aria-label="Value"
                data-autofocus={editing ? true : undefined}
              />
              {spec.secret && (
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label={shown ? 'Hide value' : 'Show value'}
                  title={shown ? 'Hide value' : 'Show value'}
                  onClick={() => setShown(!shown)}
                >
                  {shown ? <EyeOff size={14} aria-hidden="true" /> : <Eye size={14} aria-hidden="true" />}
                </Button>
              )}
            </span>
          </Field>
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
              className="sr-only"
              aria-label="File to upload"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
        )}
        {valueError && <p className="data-field-error">{valueError}</p>}
        {asksExpiry && (
          <div className="data-editor-expiry">
            <label className="text-xs text-muted-foreground" htmlFor="data-editor-expiry">
              Expires after
            </label>
            <Input
              id="data-editor-expiry"
              {...invalid(ttl === null)}
              value={ttlAmount}
              placeholder="never"
              inputMode="numeric"
              onChange={(e) => setTtlAmount(e.target.value)}
              aria-label="Expires after"
            />
            <Select value={ttlUnit} onChange={(e) => setTtlUnit(e.target.value as TtlUnit)} aria-label="Expiry unit">
              {Object.keys(TTL_UNITS).map((unit) => (
                <option key={unit} value={unit}>
                  {unit}
                </option>
              ))}
            </Select>
          </div>
        )}
        {ttl === null && <p className="data-field-error">The expiry must be a whole number above zero.</p>}
        {mustConfirm && <ConfirmInput id={mustConfirm} verb="replace its value" value={typed} onChange={setTyped} />}
        <ErrorLine failure={failure} />
      </div>
    </Dialog>
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
    <Dialog
      title={view.createLabel ?? `New ${view.noun.one}`}
      description={parent ? <>in {parentLabel}</> : view.label}
      icon={<Plus size={18} />}
      size="lg"
      onClose={onClose}
    >
      {view.create?.({ parent, busy, submit, close: onClose })}
      <ErrorLine failure={failure} />
    </Dialog>
  );
}
