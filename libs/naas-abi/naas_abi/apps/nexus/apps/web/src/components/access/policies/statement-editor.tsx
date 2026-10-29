'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react';
import type { IamAdminApi } from '@/lib/iam-admin/api';
import type { Effect, Publisher } from '@/lib/iam-admin/types';
import {
  emptyStatement,
  grantableCatalogs,
  grantablePatterns,
  hasWildcard,
  matchingActions,
  moveStatement,
  removeAt,
  suggestActions,
  suggestResources,
  typedStep,
  type EditorStatement,
  type ListedIds,
  type Suggestion,
} from './policy-editor-model';

const LISTING_DELAY_MS = 250;
import { SuggestInput } from './suggest-input';

/** A list of patterns (actions or resources) with a field that suggests the next one; with
 *  ``list``, the ids of the step being typed come from the listing as it is typed. */
function PatternList({
  label,
  values,
  onChange,
  suggest,
  list,
  note,
  placeholder,
  disabled,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  suggest: (text: string, listed: ListedIds | null) => Suggestion[];
  list?: (text: string) => Promise<ListedIds | null>;
  note?: (value: string) => string | null;
  placeholder: string;
  disabled?: boolean;
}) {
  const [text, setText] = useState('');
  const [listed, setListed] = useState<ListedIds | null>(null);
  useEffect(() => {
    if (!list || disabled) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      list(text)
        .then((found) => !cancelled && setListed(found))
        .catch(() => !cancelled && setListed(null));
    }, LISTING_DELAY_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [list, text, disabled]);
  const suggestions = useMemo(() => suggest(text, listed), [suggest, text, listed]);
  const add = (value: string) => {
    const clean = value.trim();
    if (!clean) return;
    setText('');
    if (!values.includes(clean)) onChange([...values, clean]);
  };
  // A suggestion that continues a name (ends with `:` or `/`) fills the field instead of adding.
  const pick = (suggestion: Suggestion) => {
    if (/[:/]$/.test(suggestion.value)) setText(suggestion.value);
    else add(suggestion.value);
  };
  return (
    <div className="access-policy-patterns">
      <ul className="access-policy-values" aria-label={label}>
        {values.map((value, index) => (
          <li key={value} className="access-policy-value">
            <code>{value}</code>
            {note?.(value) && <span className="access-policy-value-note">{note(value)}</span>}
            {!disabled && (
              <button
                type="button"
                className="access-policy-icon-button"
                aria-label={`Remove ${value}`}
                onClick={() => onChange(removeAt(values, index))}
              >
                <X size={12} />
              </button>
            )}
          </li>
        ))}
        {values.length === 0 && <li className="access-policy-muted">None yet</li>}
      </ul>
      {!disabled && (
        <SuggestInput
          label={`Add to ${label.toLowerCase()}`}
          value={text}
          onChange={setText}
          suggestions={suggestions}
          onPick={pick}
          onSubmit={add}
          placeholder={placeholder}
        />
      )}
    </div>
  );
}

/**
 * The visual editor of a policy's statements: effect, sid, actions and resources, with
 * autocomplete of what the caller may grant at ``scope`` only: the actions and types of
 * ``publishers`` (`GET /publishers`), the patterns they may grant them on, and the ids the
 * listing (`GET /resources`) finds as a name is typed. Never every catalog.
 */
export function StatementEditor({
  statements,
  onChange,
  api,
  scope,
  publishers = null,
  readOnly,
}: {
  statements: EditorStatement[];
  onChange: (next: EditorStatement[]) => void;
  api?: IamAdminApi;
  /** Where the policy is written: `abi:` or a container. */
  scope?: string;
  /** What the caller may grant there; null: no suggestions. */
  publishers?: Publisher[] | null;
  readOnly?: boolean;
}) {
  const catalogList = useMemo(() => grantableCatalogs(publishers ?? []), [publishers]);
  const modules = useMemo(
    () => [...new Set((publishers ?? []).flatMap((p) => p.types.flatMap((t) => (t.module ? [t.module] : []))))],
    [publishers],
  );
  const list = useMemo(() => {
    if (!api || !scope || !publishers) return undefined;
    return async (text: string): Promise<ListedIds | null> => {
      const step = typedStep(text);
      if (!step) return null;
      const type = publishers
        .flatMap((p) => p.types)
        .find((t) => t.service === step.service && t.type === step.type && (t.module ?? null) === step.module);
      // Only a type the caller may grant something of, and that is listed.
      if (!type?.listed) return null;
      const page = await api.resources({ scope, service: step.service, type: step.type, module: step.module, q: step.text });
      return {
        service: step.service,
        type: step.type,
        module: step.module,
        ids: page.items.map((item) => ({
          id: step.module ? item.id.slice(item.id.indexOf('/') + 1) : item.id,
          detail: item.description ? `${item.label}: ${item.description}` : item.label,
        })),
      };
    };
  }, [api, scope, publishers]);
  const update = (index: number, patch: Partial<EditorStatement>) =>
    onChange(statements.map((s, i) => (i === index ? { ...s, ...patch } : s)));

  return (
    <div className="access-policy-statements">
      {statements.map((statement, index) => {
        const n = index + 1;
        return (
          <fieldset key={statement.key} className="access-policy-statement" aria-label={`Statement ${n}`}>
            <legend className="access-policy-legend">Statement {n}</legend>
            <div className="access-policy-row">
              <label className="access-policy-field">
                <span>Effect</span>
                <select
                  className="access-policy-input"
                  aria-label={`Effect of statement ${n}`}
                  value={statement.effect}
                  disabled={readOnly}
                  onChange={(event) => update(index, { effect: event.target.value as Effect })}
                >
                  <option value="Allow">Allow</option>
                  <option value="Deny">Deny</option>
                </select>
              </label>
              <label className="access-policy-field access-policy-field-grow">
                <span>Sid (optional)</span>
                <input
                  type="text"
                  className="access-policy-input"
                  aria-label={`Sid of statement ${n}`}
                  value={statement.sid}
                  disabled={readOnly}
                  onChange={(event) => update(index, { sid: event.target.value })}
                />
              </label>
              {!readOnly && (
                <span className="access-policy-statement-tools">
                  <button
                    type="button"
                    className="access-policy-icon-button"
                    aria-label={`Move statement ${n} up`}
                    disabled={index === 0}
                    onClick={() => onChange(moveStatement(statements, index, -1))}
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    type="button"
                    className="access-policy-icon-button"
                    aria-label={`Move statement ${n} down`}
                    disabled={index === statements.length - 1}
                    onClick={() => onChange(moveStatement(statements, index, 1))}
                  >
                    <ArrowDown size={14} />
                  </button>
                  <button
                    type="button"
                    className="access-policy-icon-button"
                    aria-label={`Remove statement ${n}`}
                    onClick={() => onChange(removeAt(statements, index))}
                  >
                    <Trash2 size={14} />
                  </button>
                </span>
              )}
            </div>
            <div className="access-policy-field">
              <span>Actions</span>
              <PatternList
                label={`Actions of statement ${n}`}
                values={statement.actions}
                onChange={(actions) => update(index, { actions })}
                suggest={(text) => suggestActions(text, catalogList)}
                note={(value) =>
                  !readOnly && hasWildcard(value) ? `${matchingActions(value, catalogList).length} actions you may grant` : null
                }
                placeholder="service:Action, e.g. triple_store:Query"
                disabled={readOnly}
              />
            </div>
            <div className="access-policy-field">
              <span>Resources</span>
              <PatternList
                label={`Resources of statement ${n}`}
                values={statement.resources}
                onChange={(resources) => update(index, { resources })}
                suggest={(text, listed) =>
                  suggestResources(text, {
                    catalogs: catalogList,
                    actions: statement.actions,
                    grantable: grantablePatterns(publishers ?? [], statement.actions),
                    modules,
                    listed,
                  })
                }
                list={list}
                placeholder="${scope}/<service>:<type>/<id> or abi:<service>:<type>/<id>"
                disabled={readOnly}
              />
            </div>
          </fieldset>
        );
      })}
      {statements.length === 0 && <p className="access-policy-muted">No statements: this policy allows nothing.</p>}
      {!readOnly && (
        <button
          type="button"
          className="access-policy-button"
          onClick={() => onChange([...statements, emptyStatement()])}
        >
          <Plus size={14} /> Add statement
        </button>
      )}
    </div>
  );
}
