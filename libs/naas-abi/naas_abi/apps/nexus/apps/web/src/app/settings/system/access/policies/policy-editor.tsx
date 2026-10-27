'use client';

import { useState } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { CatalogsView, ModuleScopesView, PolicySource, PolicyView } from '@/lib/iam-admin/types';
import {
  POLICY_VERSION,
  fromDocument,
  toDocument,
  toText,
  type EditorStatement,
  type TextFormat,
} from './policy-editor-model';
import { PolicyText } from './policy-text';
import { StatementEditor } from './statement-editor';
import { usePolicyValidation, VALIDATION_DELAY_MS } from './use-policy-validation';

type Mode = 'visual' | 'text';

/**
 * Creates a policy (``policy`` null) or edits one. The document is edited visually or as
 * text; IAM validates it as it changes and its errors are listed under the editor. A managed
 * policy is shown read-only: IAM writes those.
 */
export function PolicyEditor({
  api,
  policy,
  catalogs,
  modules = null,
  readOnly = false,
  onSaved,
  onCancel,
  validationDelayMs = VALIDATION_DELAY_MS,
}: {
  api: IamAdminApi;
  policy: PolicyView | null;
  catalogs: CatalogsView | null;
  modules?: ModuleScopesView | null;
  readOnly?: boolean;
  onSaved: (policy: PolicyView) => void;
  onCancel: () => void;
  validationDelayMs?: number;
}) {
  const [name, setName] = useState(policy?.name ?? '');
  const [description, setDescription] = useState(policy?.description ?? '');
  const [version, setVersion] = useState(policy?.document.version ?? POLICY_VERSION);
  const [statements, setStatements] = useState<EditorStatement[]>(
    policy ? fromDocument(policy.document) : [],
  );
  const [mode, setMode] = useState<Mode>('visual');
  const [format, setFormat] = useState<TextFormat>('json');
  const [text, setText] = useState('');
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<{ message: string; errors: string[]; conflict: boolean } | null>(null);
  const [revision, setRevision] = useState(policy?.revision ?? 0);

  const source: PolicySource = mode === 'visual' ? { document: toDocument(statements, version) } : { text };
  const validation = usePolicyValidation(api, readOnly ? null : source, validationDelayMs);
  const verdict = validation.result;
  const canSave =
    !readOnly &&
    !saving &&
    name.trim() !== '' &&
    !validation.pending &&
    validation.failure === null &&
    verdict?.valid === true;

  const showText = () => {
    setText(toText(toDocument(statements, version), format));
    setSwitchError(null);
    setMode('text');
  };

  const showVisual = async () => {
    // The API reads the text (JSON or YAML); a document it refuses stays in the text view.
    try {
      const answer = await api.validatePolicy({ text });
      if (answer.valid && answer.document) {
        setStatements(fromDocument(answer.document));
        setVersion(answer.document.version);
        setSwitchError(null);
        setMode('visual');
      } else {
        setSwitchError('Fix the errors before switching to the visual editor.');
      }
    } catch (error) {
      setSwitchError(error instanceof Error ? error.message : String(error));
    }
  };

  const changeFormat = (next: TextFormat) => {
    if (verdict?.valid && verdict.document) {
      setText(toText(verdict.document, next));
      setSwitchError(null);
    } else {
      setSwitchError(`Fix the errors before converting to ${next.toUpperCase()}.`);
      return;
    }
    setFormat(next);
  };

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = policy
        ? await api.updatePolicy(policy.id, {
            ...source,
            expected_revision: revision,
            name: name.trim(),
            description,
          })
        : await api.createPolicy({ ...source, name: name.trim(), description });
      onSaved(saved);
    } catch (error) {
      if (error instanceof IamAdminError) {
        setSaveError({ message: error.message, errors: error.errors, conflict: error.status === 409 && !!policy });
      } else {
        setSaveError({ message: error instanceof Error ? error.message : String(error), errors: [], conflict: false });
      }
    } finally {
      setSaving(false);
    }
  };

  const reload = async () => {
    if (!policy) return;
    try {
      const fresh = await api.getPolicy(policy.id);
      setName(fresh.name);
      setDescription(fresh.description);
      setVersion(fresh.document.version);
      setStatements(fromDocument(fresh.document));
      setRevision(fresh.revision);
      setMode('visual');
      setSaveError(null);
    } catch (error) {
      setSaveError({ message: error instanceof Error ? error.message : String(error), errors: [], conflict: false });
    }
  };

  const errors = verdict && !verdict.valid ? verdict.errors : [];

  return (
    <section className="access-policy-editor" aria-label={policy ? `Policy ${policy.name}` : 'New policy'}>
      <header className="access-policy-editor-header">
        <h3 className="access-policy-title">{policy ? policy.name : 'New policy'}</h3>
        {policy && <code className="access-policy-id">{policy.id}</code>}
        {readOnly && (
          <span className="access-policy-badge">
            {policy?.managed ? 'Managed: IAM writes this policy' : 'Read only'}
          </span>
        )}
      </header>

      <div className="access-policy-row">
        <label className="access-policy-field access-policy-field-grow">
          <span>Name</span>
          <input
            type="text"
            className="access-policy-input"
            aria-label="Policy name"
            value={name}
            disabled={readOnly}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="access-policy-field access-policy-field-grow">
          <span>Description</span>
          <input
            type="text"
            className="access-policy-input"
            aria-label="Policy description"
            value={description}
            disabled={readOnly}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
      </div>

      <div className="access-policy-modes" role="tablist" aria-label="Editor view">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'visual'}
          className={mode === 'visual' ? 'access-policy-mode access-policy-mode-active' : 'access-policy-mode'}
          onClick={() => mode !== 'visual' && void showVisual()}
        >
          Visual
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'text'}
          className={mode === 'text' ? 'access-policy-mode access-policy-mode-active' : 'access-policy-mode'}
          onClick={() => mode !== 'text' && showText()}
        >
          YAML / JSON
        </button>
      </div>

      {mode === 'visual' ? (
        <StatementEditor
          statements={statements}
          onChange={setStatements}
          catalogs={catalogs}
          modules={modules}
          readOnly={readOnly}
        />
      ) : (
        <PolicyText text={text} onChange={setText} format={format} onFormat={changeFormat} readOnly={readOnly} />
      )}

      {switchError && (
        <p className="access-policy-notice" role="status">
          {switchError}
        </p>
      )}

      {!readOnly && (
        <div className="access-policy-validation" aria-live="polite">
          {errors.length > 0 && (
            <ul className="access-policy-errors" role="alert" aria-label="Validation errors">
              {errors.map((error) => (
                <li key={error}>
                  <AlertCircle size={14} /> {error}
                </li>
              ))}
            </ul>
          )}
          {validation.failure && <p className="access-policy-error">{validation.failure}</p>}
          {verdict?.valid && !validation.pending && (
            <p className="access-policy-ok">
              <CheckCircle2 size={14} /> IAM accepts this policy.
            </p>
          )}
          {validation.pending && <p className="access-policy-muted">Checking with IAM…</p>}
        </div>
      )}

      {saveError && (
        <div className="access-policy-error" role="alert">
          <p>{saveError.message}</p>
          {saveError.errors.length > 0 && (
            <ul>
              {saveError.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          )}
          {saveError.conflict && (
            <p>
              Someone else changed this policy since you opened it.{' '}
              <button type="button" className="access-policy-button" onClick={() => void reload()}>
                Reload their version
              </button>
            </p>
          )}
        </div>
      )}

      <footer className="access-policy-actions">
        {!readOnly && (
          <button type="button" className="access-policy-button access-policy-button-primary" disabled={!canSave} onClick={() => void save()}>
            {saving ? 'Saving…' : policy ? 'Save changes' : 'Create policy'}
          </button>
        )}
        <button type="button" className="access-policy-button" onClick={onCancel}>
          {readOnly ? 'Close' : 'Cancel'}
        </button>
      </footer>
    </section>
  );
}
