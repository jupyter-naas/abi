'use client';

/** The launch form of a workflow: one input per field of its input schema (the logic is schema-form.ts). */
import { useId } from 'react';
import { Plus, X } from 'lucide-react';
import {
  clearDrafts,
  edit,
  editNumber,
  getIn,
  pathPointer,
  type FormField,
  type FormState,
  type Issue,
  type Path,
  type Scalar,
} from './schema-form';

interface FormProps {
  state: FormState;
  issues: Issue[];
  onState: (state: FormState) => void;
}

const optionText = (option: Scalar) => String(option);

/** Select options are matched by their text: ``<select>`` values are strings. */
function pickOption(options: Scalar[], text: string): Scalar | undefined {
  return options.find((o) => optionText(o) === text);
}

function Control({
  field,
  path,
  value,
  invalid,
  label,
  props,
}: {
  field: FormField;
  path: Path;
  value: unknown;
  invalid: boolean;
  label: string;
  props: FormProps;
}) {
  const id = useId();
  const { state, onState } = props;
  const className = `data-input${invalid ? ' data-input-invalid' : ''}`;
  if (field.kind === 'boolean') {
    if (field.required || field.default !== undefined) {
      return (
        <input
          id={id}
          type="checkbox"
          className="sf-checkbox"
          aria-label={label}
          checked={value === true}
          onChange={(e) => onState(edit(state, path, e.target.checked))}
        />
      );
    }
    return (
      <select
        id={id}
        className={className}
        aria-label={label}
        value={value === undefined ? '' : String(value)}
        onChange={(e) => onState(edit(state, path, e.target.value === '' ? undefined : e.target.value === 'true'))}
      >
        <option value="">Not set</option>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }
  if (field.kind === 'enum') {
    return (
      <select
        id={id}
        className={className}
        aria-label={label}
        value={value === undefined ? '' : optionText(value as Scalar)}
        onChange={(e) => onState(edit(state, path, pickOption(field.options, e.target.value)))}
      >
        {!field.required && <option value="">Not set</option>}
        {field.required && value === undefined && (
          <option value="" disabled>
            Choose…
          </option>
        )}
        {field.options.map((o) => (
          <option key={optionText(o)} value={optionText(o)}>
            {optionText(o)}
          </option>
        ))}
      </select>
    );
  }
  if (field.kind === 'number' || field.kind === 'integer') {
    const key = pathPointer(path);
    const shown = state.drafts[key] ?? (typeof value === 'number' ? String(value) : '');
    return (
      <input
        id={id}
        className={className}
        aria-label={label}
        inputMode={field.kind === 'integer' ? 'numeric' : 'decimal'}
        autoComplete="off"
        value={shown}
        onChange={(e) => onState(editNumber(state, path, e.target.value, field.kind === 'integer'))}
      />
    );
  }
  return (
    <input
      id={id}
      className={className}
      aria-label={label}
      autoComplete="off"
      value={typeof value === 'string' ? value : ''}
      // A cleared optional string is not sent; a required one is reported as missing.
      onChange={(e) => onState(edit(state, path, e.target.value === '' && !field.required ? undefined : e.target.value))}
    />
  );
}

function ListInput({ field, path, props }: { field: FormField; path: Path; props: FormProps }) {
  const item = field.item as FormField;
  const { state, onState, issues } = props;
  const items = (getIn(state.values, path) as unknown[] | undefined) ?? [];
  return (
    <div className="sf-list">
      {items.map((value, i) => {
        const at = [...path, i];
        const problem = issues.find((x) => x.path === pathPointer(at));
        return (
          <div key={i} className="sf-list-row">
            <div className="sf-list-control">
              <Control
                field={item}
                path={at}
                value={value ?? undefined}
                invalid={Boolean(problem)}
                label={`${field.label} ${i + 1}`}
                props={props}
              />
              {problem && <p className="data-field-error">{problem.message}</p>}
            </div>
            <button
              type="button"
              className="data-icon-button"
              aria-label={`Remove ${field.label} ${i + 1}`}
              onClick={() => onState(clearDrafts(edit(state, at, undefined), path))}
            >
              <X size={14} aria-hidden="true" />
            </button>
          </div>
        );
      })}
      <button
        type="button"
        className="data-button sf-add"
        onClick={() => onState(clearDrafts(edit(state, path, [...items, item.kind === 'boolean' ? false : item.kind === 'enum' ? item.options[0] : item.kind === 'string' ? '' : null]), path))}
      >
        <Plus size={13} aria-hidden="true" /> Add {field.label.toLowerCase()}
      </button>
    </div>
  );
}

function Fields({ fields, parent, props }: { fields: FormField[]; parent: Path; props: FormProps }) {
  return (
    <>
      {fields.map((field) => {
        const path = [...parent, field.name];
        const key = pathPointer(path);
        const value = getIn(props.state.values, path);
        const problem = props.issues.find((x) => x.path === key);
        if (field.kind === 'object') {
          return (
            <fieldset key={key} className="sf-object" data-field={key}>
              <legend className="sf-label">
                {field.label}
                {field.required && <span className="sf-required" aria-hidden="true"> *</span>}
              </legend>
              {field.description && <p className="sf-help">{field.description}</p>}
              <Fields fields={field.fields} parent={path} props={props} />
              {problem && <p className="data-field-error">{problem.message}</p>}
            </fieldset>
          );
        }
        const checkbox = field.kind === 'boolean' && (field.required || field.default !== undefined);
        return (
          <div key={key} className={checkbox ? 'sf-field sf-field-inline' : 'sf-field'} data-field={key}>
            <span className="sf-label">
              {field.label}
              {field.required && <span className="sf-required"> *</span>}
            </span>
            {field.kind === 'array' ? (
              <ListInput field={field} path={path} props={props} />
            ) : (
              <Control field={field} path={path} value={value} invalid={Boolean(problem)} label={field.label} props={props} />
            )}
            {field.description && <p className="sf-help">{field.description}</p>}
            {problem && <p className="data-field-error">{problem.message}</p>}
          </div>
        );
      })}
    </>
  );
}

export function SchemaForm({ fields, ...props }: { fields: FormField[] } & FormProps) {
  return (
    <div className="sf" role="group" aria-label="Input">
      <Fields fields={fields} parent={[]} props={props} />
    </div>
  );
}
