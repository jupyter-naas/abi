'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { CatalogsView, ModuleScopesView, PolicySource, PolicyView } from '@/lib/iam-admin/types';
import { PLATFORM_ACCESS_SCOPE, ownerOf, type AccessScope } from '../access-scope';
import { ROLE_LABELS, roleOfPolicy } from '../roles/role-change';
import { builderStatements, refusedItems, splitStatements, type BuilderGroup } from './builder/builder-model';
import { PolicyBuilder } from './builder/policy-builder';
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

type Mode = 'builder' | 'visual' | 'text';

type SaveError = { message: string; errors: string[]; conflict: boolean; refused: string[] };

/** The parent of ``policy``: named when the API read it with the policy, else by its id. */
function parentOf(policy: PolicyView | null): { id: string; name: string | null } | null {
  if (!policy?.parent_id) return null;
  return { id: policy.parent_id, name: policy.parent?.id === policy.parent_id ? policy.parent.name : null };
}

/**
 * Creates a policy (``policy`` null) owned by ``scope``, or edits one. With ``builder`` (what
 * the caller may grant there), the policy is chosen as checkboxes, and a new one may start
 * from a built-in role; the statement editor and the text view (YAML or JSON) are the advanced
 * modes. IAM validates the document as it changes, as a policy of that scope, and a refusal
 * at save that names an item is shown beside it. A managed policy is shown read-only.
 */
export function PolicyEditor({
  api,
  policy,
  catalogs,
  modules = null,
  builder = null,
  scope = PLATFORM_ACCESS_SCOPE,
  roles = [],
  readOnly = false,
  onSaved,
  onCancel,
  validationDelayMs = VALIDATION_DELAY_MS,
}: {
  api: IamAdminApi;
  policy: PolicyView | null;
  catalogs: CatalogsView | null;
  modules?: ModuleScopesView | null;
  /** The builder's items; null: no builder (it could not be loaded, or the caller grants nothing). */
  builder?: BuilderGroup[] | null;
  scope?: AccessScope;
  /** The built-in roles a new policy may start from: those the caller's policy list holds. */
  roles?: PolicyView[];
  readOnly?: boolean;
  onSaved: (policy: PolicyView) => void;
  onCancel: () => void;
  validationDelayMs?: number;
}) {
  const [name, setName] = useState(policy?.name ?? '');
  const [description, setDescription] = useState(policy?.description ?? '');
  const [version, setVersion] = useState(policy?.document.version ?? POLICY_VERSION);
  const [statements, setStatements] = useState<EditorStatement[]>(policy ? fromDocument(policy.document) : []);
  const [mode, setMode] = useState<Mode>(() => {
    if (!builder) return 'visual';
    if (!policy) return 'builder';
    // An existing policy opens in the builder when the builder shows all of it.
    return splitStatements(builder, policy.document.statements).rest.length === 0 ? 'builder' : 'visual';
  });
  const [format, setFormat] = useState<TextFormat>('json');
  const [text, setText] = useState('');
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<SaveError | null>(null);
  const [revision, setRevision] = useState(policy?.revision ?? 0);
  // The parent stays as it is on save (the update leaves it out); a reload shows the newer one.
  const [parent, setParent] = useState(() => parentOf(policy));
  const [starting, setStarting] = useState('');
  const owner = scope.value ?? undefined;

  const doc = useMemo(() => toDocument(statements, version), [statements, version]);

  // The builder may arrive after the editor opened (what the caller may grant is read once the
  // list is): a new policy nothing was written in yet opens in it then.
  useEffect(() => {
    if (builder && !policy && mode === 'visual' && statements.length === 0) setMode('builder');
    // Only the builder's arrival decides it, not later edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [builder]);
  const split = useMemo(() => (builder ? splitStatements(builder, doc.statements) : null), [builder, doc]);

  const source: PolicySource = mode === 'text' ? { text } : { document: doc };
  const validation = usePolicyValidation(api, readOnly ? null : source, validationDelayMs, owner);
  const verdict = validation.result;
  const canSave =
    !readOnly &&
    !saving &&
    name.trim() !== '' &&
    !validation.pending &&
    validation.failure === null &&
    verdict?.valid === true;

  const toggle = (keys: string[], on: boolean) => {
    if (!builder || !split) return;
    const selected = new Set(split.selected);
    for (const key of keys) {
      if (on) selected.add(key);
      else selected.delete(key);
    }
    setStatements(fromDocument({ version, statements: [...split.rest, ...builderStatements(builder, selected, split.rest)] }));
    setSaveError(null);
  };

  // Nothing is an empty policy again: what a role brought never stays behind.
  const startFrom = (policyId: string) => {
    setStarting(policyId);
    const role = roles.find((r) => r.id === policyId);
    setStatements(role ? fromDocument(role.document) : []);
    setVersion(role ? role.document.version : POLICY_VERSION);
    setSwitchError(null);
    setSaveError(null);
  };

  const showText = () => {
    setText(toText(doc, format));
    setSwitchError(null);
    setMode('text');
  };

  const showForm = async (next: 'builder' | 'visual') => {
    if (mode !== 'text') {
      setMode(next);
      return;
    }
    // The API reads the text (JSON or YAML); a document it refuses stays in the text view.
    try {
      const answer = await api.validatePolicy({ text }, owner);
      if (answer.valid && answer.document) {
        setStatements(fromDocument(answer.document));
        setVersion(answer.document.version);
        setSwitchError(null);
        setMode(next);
      } else {
        setSwitchError('Fix the errors before leaving the text view.');
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
        : await api.createPolicy({ ...source, name: name.trim(), description, ...(owner ? { scope: owner } : {}) });
      onSaved(saved);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSaveError({
        message,
        errors: error instanceof IamAdminError ? error.errors : [],
        conflict: error instanceof IamAdminError && error.status === 409 && !!policy,
        refused: builder ? refusedItems(builder, message, ownerOf(scope)) : [],
      });
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
      setParent(parentOf(fresh));
      setMode(builder ? 'builder' : 'visual');
      setSaveError(null);
    } catch (error) {
      setSaveError({ message: error instanceof Error ? error.message : String(error), errors: [], conflict: false, refused: [] });
    }
  };

  const errors = verdict && !verdict.valid ? verdict.errors : [];
  const refused = Object.fromEntries((saveError?.refused ?? []).map((key) => [key, saveError!.message]));
  const tab = (id: Mode, label: string, open: () => void) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === id}
      className={mode === id ? 'access-policy-mode access-policy-mode-active' : 'access-policy-mode'}
      onClick={() => mode !== id && open()}
    >
      {label}
    </button>
  );

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
      {parent && (
        <p className="access-policy-parent" aria-label="Parent policy">
          Sub-policy of <strong>{parent.name ?? parent.id}</strong>
          {parent.name && <code className="access-policy-id">{parent.id}</code>}: it never grants more than its
          parent does.
        </p>
      )}

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
        {!policy && !readOnly && roles.length > 0 && (
          <label className="access-policy-field">
            <span>Start from</span>
            <select
              className="access-policy-input"
              aria-label="Start from a built-in role"
              value={starting}
              onChange={(event) => startFrom(event.target.value)}
            >
              <option value="">Nothing</option>
              {roles.map((role) => (
                <option key={role.id} value={role.id}>
                  The {ROLE_LABELS[roleOfPolicy(role.id)!] ?? role.name} role
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="access-policy-modes" role="tablist" aria-label="Editor view">
        {builder && tab('builder', 'Builder', () => void showForm('builder'))}
        {tab('visual', builder ? 'Statements' : 'Visual', () => void showForm('visual'))}
        {tab('text', 'YAML / JSON', showText)}
      </div>

      {mode === 'builder' && builder && split ? (
        <PolicyBuilder
          groups={builder}
          selected={split.selected}
          kept={split.rest.length}
          onToggle={toggle}
          refused={refused}
          readOnly={readOnly}
        />
      ) : mode === 'visual' ? (
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
          {/* Valid is not granted: once a save was refused, the refusal alone speaks. */}
          {verdict?.valid && !validation.pending && !saveError && (
            <p className="access-policy-ok">
              <CheckCircle2 size={14} /> Valid policy.
            </p>
          )}
          {validation.pending && <p className="access-policy-muted">Checking with IAM…</p>}
        </div>
      )}

      {saveError && (
        <div className="access-policy-error" role="alert" data-save-error="">
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
