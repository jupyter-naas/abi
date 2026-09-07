'use client';

import { useEffect, useState } from 'react';

type InvoiceAnnotationCellProps = {
  value: string;
  type: 'date' | 'text' | 'textarea';
  ariaLabel: string;
  placeholder?: string;
  onSave: (value: string) => void;
};

const inputClass =
  'w-full min-w-[8rem] rounded border border-transparent bg-transparent px-1.5 py-0.5 text-sm text-[var(--text)] transition-colors hover:border-[var(--border)] focus:border-[var(--secondary)] focus:bg-[var(--surface)] focus:outline-none';

const textareaClass =
  `${inputClass} min-w-[12rem] max-w-md resize-y whitespace-pre-wrap leading-snug`;

/** Accepts `YYYY-MM-DD` or `DD/MM/YYYY` pasted text (native date inputs ignore paste). */
function normalizePastedDate(text: string): string | null {
  const trimmed = text.trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (iso) {
    return trimmed;
  }
  const fr = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (fr) {
    return `${fr[3]}-${fr[2].padStart(2, '0')}-${fr[1].padStart(2, '0')}`;
  }
  return null;
}

function rowCountFor(value: string): number {
  const lines = value.split('\n').length;
  return Math.min(8, Math.max(2, lines));
}

/** Editable table cell for user-maintained invoice follow-up fields. Commits on blur or Enter. */
export function InvoiceAnnotationCell({
  value,
  type,
  ariaLabel,
  placeholder,
  onSave,
}: InvoiceAnnotationCellProps) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const commit = () => {
    if (draft !== value) {
      onSave(draft);
    }
  };

  if (type === 'textarea') {
    return (
      <textarea
        value={draft}
        aria-label={ariaLabel}
        placeholder={placeholder}
        rows={rowCountFor(draft)}
        className={textareaClass}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          // Ctrl/Cmd+Enter commits; plain Enter inserts a new line.
          if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            event.currentTarget.blur();
          }
        }}
      />
    );
  }

  return (
    <input
      type={type}
      value={draft}
      aria-label={ariaLabel}
      placeholder={placeholder}
      className={inputClass}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.currentTarget.blur();
        }
        // Native date inputs have no text selection: wire Ctrl/Cmd+C manually.
        if (
          type === 'date' &&
          (event.ctrlKey || event.metaKey) &&
          event.key.toLowerCase() === 'c'
        ) {
          void navigator.clipboard?.writeText(draft);
        }
      }}
      onPaste={(event) => {
        if (type !== 'date') {
          return;
        }
        const pasted = normalizePastedDate(event.clipboardData.getData('text'));
        if (pasted) {
          event.preventDefault();
          setDraft(pasted);
          if (pasted !== value) {
            onSave(pasted);
          }
        }
      }}
    />
  );
}
