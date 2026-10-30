'use client';

import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { IamAdminError, type IamAdminApi } from '@/lib/iam-admin/api';
import type { PolicyRef, PolicySource, PolicyStatement, PolicyView, Publisher } from '@/lib/iam-admin/types';
import { PLATFORM_ACCESS_SCOPE, ownerOf, type AccessScope } from '../access-scope';
import { ROLE_LABELS, roleOfPolicy } from '../roles/role-change';
import {
  allTypes,
  builderPublishers,
  builderStatements,
  grantableOn,
  refusedTypes,
  splitStatements,
  type BuilderPublisher,
  type Choice,
  type Choices,
} from './builder/builder-model';
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

/** What the caller may grant here, loaded for the scope and the parent. */
type Grantable =
  | { state: 'loading' }
  | { state: 'ready'; publishers: Publisher[]; builder: BuilderPublisher[] }
  /** ``refused``: IAM's verdict on the parent (not derivable, not its owner's, too deep, not
   *  found); else a failure to retry, which does not block a save IAM judges anyway. */
  | { state: 'failed'; message: string; refused: boolean };

/** The statuses that are IAM's refusal of a parent: denied, not found, or invalid there. */
const REFUSALS = new Set([403, 404, 422]);

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** The parent of ``policy``: named when the API read it with the policy, else by its id. */
function parentOf(policy: PolicyView | null): { id: string; name: string | null } | null {
  if (!policy?.parent_id) return null;
  return { id: policy.parent_id, name: policy.parent?.id === policy.parent_id ? policy.parent.name : null };
}

/**
 * Creates a policy (``policy`` null) owned by ``scope``, or edits one. The builder offers what
 * the caller may grant there by publisher (`GET /publishers`), within the parent of a
 * sub-policy: a new policy may be a sub-policy of one of ``parents`` (IAM accepts only one the
 * caller holds there), or start from a built-in role. The statement editor and the text view
 * (YAML or JSON) are the advanced modes. IAM validates the document as it changes, as a policy
 * of that scope, and a refusal at save that names a type's choice is shown beside it. A managed
 * policy is shown read-only.
 */
export function PolicyEditor({
  api,
  policy,
  scope = PLATFORM_ACCESS_SCOPE,
  roles = [],
  parents = [],
  readOnly = false,
  onSaved,
  onCancel,
  onOpen,
  validationDelayMs = VALIDATION_DELAY_MS,
}: {
  api: IamAdminApi;
  policy: PolicyView | null;
  scope?: AccessScope;
  /** The built-in roles a new policy may start from: those the caller's policy list holds. */
  roles?: PolicyView[];
  /** The policies a new one may be a sub-policy of: those listed at this scope. */
  parents?: PolicyView[];
  readOnly?: boolean;
  onSaved: (policy: PolicyView) => void;
  onCancel: () => void;
  /** Opens another policy (a parent or a sub-policy) by its id. */
  onOpen?: (id: string) => void;
  validationDelayMs?: number;
}) {
  const [name, setName] = useState(policy?.name ?? '');
  const [description, setDescription] = useState(policy?.description ?? '');
  const [version, setVersion] = useState(policy?.document.version ?? POLICY_VERSION);
  const [statements, setStatements] = useState<EditorStatement[]>(policy ? fromDocument(policy.document) : []);
  const [mode, setMode] = useState<Mode>('visual');
  // Until the user picks a view, the editor opens in the builder once it can show the policy.
  const [picked, setPicked] = useState(false);
  const [format, setFormat] = useState<TextFormat>('json');
  const [text, setText] = useState('');
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<SaveError | null>(null);
  const [revision, setRevision] = useState(policy?.revision ?? 0);
  // The parent stays as it is on save (the update leaves it out); a reload shows the newer one.
  const [parent, setParent] = useState(() => parentOf(policy));
  const [subPolicies, setSubPolicies] = useState<PolicyRef[]>(policy?.sub_policies ?? []);
  // A new policy's parent, chosen here.
  const [newParent, setNewParent] = useState('');
  const [starting, setStarting] = useState('');
  const [grantable, setGrantable] = useState<Grantable>({ state: 'loading' });
  const [choices, setChoices] = useState<Choices>({});
  const [kept, setKept] = useState<PolicyStatement[]>([]);
  // Bumped by Retry: what may be granted is read again.
  const [attempt, setAttempt] = useState(0);
  const owner = scope.value ?? undefined;
  const parentId = policy ? parent?.id ?? null : newParent || null;

  const doc = useMemo(() => toDocument(statements, version), [statements, version]);
  const publishers = grantable.state === 'ready' ? grantable.publishers : null;
  const builder = grantable.state === 'ready' ? grantable.builder : null;

  // What the caller may grant here, within the parent: the builder and the suggestions.
  useEffect(() => {
    if (readOnly) return;
    let cancelled = false;
    setGrantable({ state: 'loading' });
    // A new sub-policy asks IAM's verdict on its parent as creating it would: derive, owner, depth.
    api
      .publishers(ownerOf(scope), parentId, { derive: !policy && !!parentId })
      .then((view) => {
        if (!cancelled) setGrantable({ state: 'ready', publishers: view.publishers, builder: builderPublishers(view) });
      })
      .catch((error) => {
        if (cancelled) return;
        const refused = !!parentId && error instanceof IamAdminError && REFUSALS.has(error.status);
        setGrantable({ state: 'failed', message: message(error), refused });
      });
    return () => {
      cancelled = true;
    };
    // An existing policy's parent is read once with it; the policy itself does not change here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, scope, parentId, readOnly, attempt]);

  // A policy read one by one names its parent and its sub-policies.
  useEffect(() => {
    if (!policy || policy.sub_policies !== undefined) return;
    let cancelled = false;
    api
      .getPolicy(policy.id)
      .then((fresh) => {
        if (cancelled) return;
        setSubPolicies(fresh.sub_policies ?? []);
        if (fresh.parent_id === policy.parent_id) setParent(parentOf(fresh));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [api, policy]);

  /** The document read into the builder's choices, what it cannot show kept as statements.
   *  With ``unfinished`` (the choices before a reload), a type's actions or resources picked
   *  without the other stay, as far as the type is still offered. */
  const intoBuilder = (from: PolicyStatement[], offered: BuilderPublisher[], unfinished: Choices = {}) => {
    const split = splitStatements(offered, from);
    const next = { ...split.choices };
    for (const type of allTypes(offered)) {
      const before = unfinished[type.key];
      if (!before || next[type.key] || (before.actions.length > 0 && before.resources.length > 0)) continue;
      const actions = before.actions.filter((a) => type.actions.some((offeredAction) => offeredAction.action === a));
      const resources = before.resources.filter((r) => grantableOn(type, r));
      if (actions.length || resources.length) next[type.key] = { actions, resources };
    }
    setChoices(next);
    setKept(split.rest);
    return split;
  };

  // When what may be granted arrives (or changes with the parent): the builder reads the
  // document again, and opens on it unless a view was picked (an existing policy only when
  // the builder shows all of it).
  useEffect(() => {
    if (!builder) {
      if (grantable.state === 'failed' && mode === 'builder') setMode('visual');
      return;
    }
    const split = intoBuilder(doc.statements, builder, choices);
    if (!picked && mode !== 'text' && (policy ? split.rest.length === 0 : statements.length === 0 || split.rest.length === 0)) {
      setMode('builder');
    }
    // Only the arrival decides it, not later edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [grantable]);

  const source: PolicySource = mode === 'text' ? { text } : { document: doc };
  const validation = usePolicyValidation(api, readOnly ? null : source, validationDelayMs, owner);
  const verdict = validation.result;
  const parentRefused = !policy && !!newParent && grantable.state === 'failed' && grantable.refused;
  const canSave =
    !readOnly &&
    !saving &&
    !parentRefused &&
    name.trim() !== '' &&
    !validation.pending &&
    validation.failure === null &&
    verdict?.valid === true;

  const change = (key: string, choice: Choice) => {
    if (!builder) return;
    const next = { ...choices, [key]: choice };
    setChoices(next);
    setStatements(fromDocument({ version, statements: [...kept, ...builderStatements(builder, next, kept)] }));
    setSaveError(null);
  };

  // Nothing is an empty policy again: what a role brought never stays behind.
  const startFrom = (policyId: string) => {
    setStarting(policyId);
    const role = roles.find((r) => r.id === policyId);
    const next = role ? role.document : { version: POLICY_VERSION, statements: [] };
    setStatements(fromDocument(next));
    setVersion(next.version);
    if (builder) intoBuilder(next.statements, builder);
    setSwitchError(null);
    setSaveError(null);
  };

  const showText = () => {
    setText(toText(doc, format));
    setSwitchError(null);
    setPicked(true);
    setMode('text');
  };

  const showForm = async (next: 'builder' | 'visual') => {
    setPicked(true);
    if (mode !== 'text') {
      if (next === 'builder' && builder) intoBuilder(doc.statements, builder);
      setMode(next);
      return;
    }
    // The API reads the text (JSON or YAML); a document it refuses stays in the text view.
    try {
      const answer = await api.validatePolicy({ text }, owner);
      if (answer.valid && answer.document) {
        setStatements(fromDocument(answer.document));
        setVersion(answer.document.version);
        if (next === 'builder' && builder) intoBuilder(answer.document.statements, builder);
        setSwitchError(null);
        setMode(next);
      } else {
        setSwitchError('Fix the errors before leaving the text view.');
      }
    } catch (error) {
      setSwitchError(message(error));
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
        : await api.createPolicy({
            ...source,
            name: name.trim(),
            description,
            ...(owner ? { scope: owner } : {}),
            ...(newParent ? { parent: newParent } : {}),
          });
      onSaved(saved);
    } catch (error) {
      const text = message(error);
      setSaveError({
        message: text,
        errors: error instanceof IamAdminError ? error.errors : [],
        conflict: error instanceof IamAdminError && error.status === 409 && !!policy,
        refused: builder ? refusedTypes(builder, choices, text, ownerOf(scope)) : [],
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
      setSubPolicies(fresh.sub_policies ?? []);
      if (builder) intoBuilder(fresh.document.statements, builder);
      setMode(builder ? 'builder' : 'visual');
      setSaveError(null);
    } catch (error) {
      setSaveError({ message: message(error), errors: [], conflict: false, refused: [] });
    }
  };

  const errors = verdict && !verdict.valid ? verdict.errors : [];
  const refused = Object.fromEntries((saveError?.refused ?? []).map((key) => [key, saveError!.message]));
  const candidates = parents.filter((p) => !p.managed && p.id !== policy?.id);
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
          Sub-policy of{' '}
          {onOpen ? (
            <button type="button" className="access-policy-link" onClick={() => onOpen(parent.id)}>
              {parent.name ?? parent.id}
            </button>
          ) : (
            <strong>{parent.name ?? parent.id}</strong>
          )}
          {parent.name && <code className="access-policy-id">{parent.id}</code>}: it never grants more than its
          parent does.
        </p>
      )}
      {subPolicies.length > 0 && (
        <div className="access-policy-parent" aria-label="Sub-policies">
          <span>Sub-policies, each within this one:</span>
          <ul className="access-policy-subs">
            {subPolicies.map((sub) => (
              <li key={sub.id}>
                {onOpen ? (
                  <button type="button" className="access-policy-link" onClick={() => onOpen(sub.id)}>
                    {sub.name ?? sub.id}
                  </button>
                ) : (
                  <span>{sub.name ?? sub.id}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
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
        {!policy && !readOnly && candidates.length > 0 && (
          <label className="access-policy-field">
            <span>Sub-policy of</span>
            <select
              className="access-policy-input"
              aria-label="Sub-policy of"
              value={newParent}
              onChange={(event) => {
                setNewParent(event.target.value);
                setSaveError(null);
              }}
            >
              <option value="">No parent</option>
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
            </select>
          </label>
        )}
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
      {newParent && !policy && (
        <p className={parentRefused ? 'access-policy-error' : 'access-policy-muted'} role={parentRefused ? 'alert' : 'status'} data-parent-verdict="">
          {parentRefused
            ? grantable.message
            : grantable.state === 'loading'
              ? 'Asking IAM about this parent…'
              : 'The builder offers only what the parent allows and you may grant.'}
        </p>
      )}

      <div className="access-policy-modes" role="tablist" aria-label="Editor view">
        {builder && tab('builder', 'Builder', () => void showForm('builder'))}
        {tab('visual', builder ? 'Statements' : 'Visual', () => void showForm('visual'))}
        {tab('text', 'YAML / JSON', showText)}
      </div>

      {mode === 'builder' && !builder ? (
        // While what may be granted is read again (a new parent): nothing to edit yet.
        <p className="access-policy-muted" role="status" data-builder-loading="">
          Loading what you may grant…
        </p>
      ) : mode === 'builder' && builder ? (
        <PolicyBuilder
          api={api}
          scope={ownerOf(scope)}
          validateAt={owner}
          publishers={builder}
          choices={choices}
          onChange={change}
          kept={kept.length}
          refused={refused}
          delayMs={validationDelayMs}
        />
      ) : mode === 'visual' ? (
        <StatementEditor
          statements={statements}
          onChange={setStatements}
          api={api}
          scope={ownerOf(scope)}
          publishers={publishers}
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
      {!readOnly && grantable.state === 'failed' && !parentRefused && (
        <p className="access-policy-notice" role="status" data-grantable-failure="">
          No builder or suggestions: {grantable.message}{' '}
          <button type="button" className="access-policy-button" onClick={() => setAttempt((n) => n + 1)}>
            Retry
          </button>
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

