'use client';

import type { TextFormat } from './policy-editor-model';

/** The policy as text, JSON or YAML: what IAM reads when it is saved. */
export function PolicyText({
  text,
  onChange,
  format,
  onFormat,
  readOnly,
}: {
  text: string;
  onChange: (text: string) => void;
  format: TextFormat;
  onFormat: (format: TextFormat) => void;
  readOnly?: boolean;
}) {
  return (
    <div className="access-policy-text">
      <label className="access-policy-field">
        <span>Format</span>
        <select
          className="access-policy-input"
          aria-label="Text format"
          value={format}
          disabled={readOnly}
          onChange={(event) => onFormat(event.target.value as TextFormat)}
        >
          <option value="json">JSON</option>
          <option value="yaml">YAML</option>
        </select>
      </label>
      <textarea
        className="access-policy-textarea"
        aria-label="Policy document"
        spellCheck={false}
        rows={18}
        value={text}
        readOnly={readOnly}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
