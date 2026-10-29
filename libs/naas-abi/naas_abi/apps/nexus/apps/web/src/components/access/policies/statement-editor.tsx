'use client';

import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, Plus, Trash2, X } from 'lucide-react';
import type { CatalogsView, Effect, ModuleScopesView } from '@/lib/iam-admin/types';
import {
  emptyStatement,
  hasWildcard,
  matchingActions,
  moveStatement,
  removeAt,
  suggestActions,
  suggestResources,
  type EditorStatement,
  type Suggestion,
} from './policy-editor-model';
import { SuggestInput } from './suggest-input';

/** A list of patterns (actions or resources) with a field that suggests the next one. */
function PatternList({
  label,
  values,
  onChange,
  suggest,
  note,
  placeholder,
  disabled,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  suggest: (text: string) => Suggestion[];
  note?: (value: string) => string | null;
  placeholder: string;
  disabled?: boolean;
}) {
  const [text, setText] = useState('');
  const suggestions = useMemo(() => suggest(text), [suggest, text]);
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

/** The visual editor of a policy's statements: effect, sid, actions and resources, with
 *  autocomplete from the action catalogs and the resource-name grammar. */
export function StatementEditor({
  statements,
  onChange,
  catalogs,
  modules = null,
  readOnly,
}: {
  statements: EditorStatement[];
  onChange: (next: EditorStatement[]) => void;
  catalogs: CatalogsView | null;
  modules?: ModuleScopesView | null;
  readOnly?: boolean;
}) {
  const catalogList = catalogs?.catalogs ?? [];
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
                  hasWildcard(value) ? `${matchingActions(value, catalogList).length} actions` : null
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
                suggest={(text) => suggestResources(text, { catalogs, actions: statement.actions, modules })}
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
