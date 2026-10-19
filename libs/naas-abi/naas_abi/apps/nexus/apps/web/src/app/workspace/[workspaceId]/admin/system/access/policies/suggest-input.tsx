'use client';

import { useId, useState } from 'react';
import type { Suggestion } from './policy-editor-model';

/**
 * A text field with a list of suggestions under it. Picking one calls `onPick`; Enter calls
 * `onSubmit` with what was typed (the caller decides whether that becomes a value).
 */
export function SuggestInput({
  label,
  value,
  onChange,
  suggestions,
  onPick,
  onSubmit,
  placeholder,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (text: string) => void;
  suggestions: Suggestion[];
  onPick: (suggestion: Suggestion) => void;
  onSubmit?: (text: string) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const shown = open && suggestions.length > 0;
  return (
    <div className="access-policy-suggest">
      <input
        type="text"
        className="access-policy-input"
        role="combobox"
        aria-label={label}
        aria-expanded={shown}
        aria-controls={shown ? listId : undefined}
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
          if (event.key === 'Enter' && onSubmit) {
            event.preventDefault();
            onSubmit(value);
            setOpen(false);
          }
        }}
      />
      {shown && (
        <ul id={listId} className="access-policy-suggestions" role="listbox" aria-label={`${label} suggestions`}>
          {suggestions.map((suggestion) => (
            <li key={suggestion.value} role="option" aria-selected={false}>
              <button
                type="button"
                className="access-policy-suggestion"
                // Keeps the field focused: its blur would close the list before the click lands.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onPick(suggestion);
                  setOpen(false);
                }}
              >
                <span className="access-policy-suggestion-value">{suggestion.value}</span>
                {suggestion.badge && <span className="access-policy-badge">{suggestion.badge}</span>}
                {suggestion.detail && (
                  <span className="access-policy-suggestion-detail">{suggestion.detail}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
