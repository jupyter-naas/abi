'use client';

/**
 * Batch changes of access on a settings table (Access › Features, Core Services): a checkbox per
 * row and one in the header (select all, or none), and a bar while rows are selected that sets
 * their access to one level, asked first in a modal. The page applies the level (`onApply`) in one
 * write and says which rows the level does not fit (`bulkSkipped`).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { ModalBackdrop } from '@/components/ui/dialogs';
import { LEVEL_LABELS, type AccessLevel } from '@/lib/access-model/access-levels';
import '@/app/organizations/[orgId]/settings/users/users.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import './bulk-access.css';

export type RowSelection = {
  selected: ReadonlySet<string>;
  toggle: (key: string) => void;
  /** Select every one of `keys`, or none of them when they all are. */
  toggleAll: (keys: readonly string[]) => void;
  clear: () => void;
};

/** The rows selected among `keys` (a row gone from the table leaves the selection). */
export function useRowSelection(keys: readonly string[]): RowSelection {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const present = useMemo(() => new Set(keys), [keys]);
  useEffect(() => {
    setSelected((current) => {
      const kept = [...current].filter((key) => present.has(key));
      return kept.length === current.size ? current : new Set(kept);
    });
  }, [present]);
  const toggle = useCallback(
    (key: string) =>
      setSelected((current) => {
        const next = new Set(current);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      }),
    []
  );
  const toggleAll = useCallback(
    (all: readonly string[]) =>
      setSelected((current) => (all.length > 0 && all.every((key) => current.has(key)) ? new Set() : new Set(all))),
    []
  );
  const clear = useCallback(() => setSelected(new Set()), []);
  return { selected, toggle, toggleAll, clear };
}

/** The header's checkbox: every row shown selected, some (indeterminate), or none. */
export function SelectAllCell({
  selection,
  keys,
  noun,
  disabled = false,
}: {
  selection: RowSelection;
  keys: readonly string[];
  noun: string;
  disabled?: boolean;
}) {
  const chosen = keys.filter((key) => selection.selected.has(key)).length;
  const all = keys.length > 0 && chosen === keys.length;
  // The settings' square checkbox, centred in its column.
  return (
    <th className="settings-select-cell" data-select-column="">
      <Checkbox
        aria-label={all ? `Select no ${noun}` : `Select every ${noun}`}
        checked={all}
        indeterminate={chosen > 0 && !all}
        disabled={disabled || keys.length === 0}
        data-action="select-all"
        onCheckedChange={() => selection.toggleAll(keys)}
      />
    </th>
  );
}

export function SelectRowCell({
  selection,
  rowKey,
  label,
  disabled = false,
}: {
  selection: RowSelection;
  rowKey: string;
  label: string;
  disabled?: boolean;
}) {
  // A click on it selects the row, never opens it (a row that opens its page).
  return (
    <td className="settings-select-cell" onClick={(event) => event.stopPropagation()}>
      <Checkbox
        aria-label={`Select ${label}`}
        checked={selection.selected.has(rowKey)}
        disabled={disabled}
        data-select-row={rowKey}
        onCheckedChange={() => selection.toggle(rowKey)}
      />
    </td>
  );
}

/** "1 of the 3 features cannot take this level and stays as it is.", or null when all can. */
export function bulkSkipped(
  total: number,
  skipped: number,
  noun: string,
  change = 'this level',
  plural = `${noun}s`
): string | null {
  if (skipped === 0) return null;
  return `${skipped} of the ${total} ${total === 1 ? noun : plural} cannot take ${change} and ${
    skipped === 1 ? 'stays' : 'stay'
  } as ${skipped === 1 ? 'it is' : 'they are'}.`;
}

/** One choice of a batch bar: a level, or an action (Offer, Take back). */
export type BulkAction = {
  id: string;
  /** The button. */
  label: string;
  /** The modal's question, for `count` rows ("Set access to Read for 3 features?"). */
  question: (count: number, plural: string) => string;
  /** What the change does, said under the question. */
  detail?: (count: number) => string;
  /** The modal's confirm button ("Set to Read", "Offer"). */
  confirm: string;
};

/**
 * The two actions of a batch bar on an on/off column (Enabled, Offered, Shown...), in the page's
 * words: `on` (Enable, Offer, Show) and `off` (Disable, Take back, Hide). Ids `on` and `off`.
 */
export function onOffActions(words: { on: string; off: string }, detail?: (on: boolean, count: number) => string): BulkAction[] {
  return (['on', 'off'] as const).map((id) => {
    const word = id === 'on' ? words.on : words.off;
    return {
      id,
      label: word,
      question: (count, plural) => `${word} ${count} ${plural}?`,
      detail: detail ? (count) => detail(id === 'on', count) : undefined,
      confirm: word,
    };
  });
}

/**
 * While rows are selected: how many, the actions on them (`intro` before them), and Clear. An
 * action opens a modal that names the change; Confirm applies it (`onApply`) and clears the
 * selection.
 */
export function BulkBar({
  selection,
  noun,
  intro,
  actions,
  onApply,
  skippedFor,
  disabled = false,
  change,
  plural: pluralNoun,
}: {
  selection: RowSelection;
  /** Singular: "feature", "service", "module". */
  noun: string;
  /** Its plural when not `noun` + s ("ontologies", "entries"). */
  plural?: string;
  intro?: string;
  actions: readonly BulkAction[];
  onApply: (id: string) => void | Promise<void>;
  /** How many of the selected rows the action does not fit (left as they are). */
  skippedFor?: (id: string) => number;
  disabled?: boolean;
  /** What a skipped row cannot take, in the modal: "this level" by default, "this change"... */
  change?: string;
}) {
  const [asked, setAsked] = useState<BulkAction | null>(null);
  const count = selection.selected.size;
  if (count === 0) return null;
  const plural = count === 1 ? noun : (pluralNoun ?? `${noun}s`);
  const skipped = asked && skippedFor ? bulkSkipped(count, skippedFor(asked.id), noun, change, pluralNoun) : null;
  return (
    <div className="org-settings-general-draft" role="status" data-bulk-bar="">
      <p className="org-settings-general-draft-text">
        {count} {plural} selected
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {intro ? <span className="text-xs text-muted-foreground">{intro}</span> : null}
        {actions.map((action) => (
          <button
            key={action.id}
            type="button"
            className="org-settings-users-secondary-button"
            data-level={action.id}
            data-bulk-action={action.id}
            disabled={disabled}
            onClick={() => setAsked(action)}
          >
            {action.label}
          </button>
        ))}
        <button type="button" className="org-settings-general-draft-discard" onClick={selection.clear} disabled={disabled}>
          Clear selection
        </button>
      </div>
      <ModalBackdrop open={asked !== null} onClose={() => setAsked(null)}>
        <div className="border border-border bg-background p-6 shadow-2xl" role="dialog" aria-modal="true" data-bulk-confirm="">
          <h3 className="text-base font-semibold text-foreground">{asked?.question(count, plural)}</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {asked?.detail?.(count) ?? 'The change is made in one save.'}
            {skipped ? ` ${skipped}` : ''}
          </p>
          <div className="mt-6 flex justify-end gap-2">
            <button type="button" className="org-settings-users-secondary-button" onClick={() => setAsked(null)}>
              Cancel
            </button>
            <button
              type="button"
              className="org-settings-primary-button"
              onClick={() => {
                const action = asked;
                setAsked(null);
                if (!action) return;
                void Promise.resolve(onApply(action.id)).then(() => selection.clear());
              }}
            >
              {asked?.confirm}
            </button>
          </div>
        </div>
      </ModalBackdrop>
    </div>
  );
}

/** The batch bar of a table of access levels: set the selected rows to one level. */
export function BulkAccessBar({
  selection,
  noun,
  levels,
  onApply,
  skippedFor,
  disabled = false,
}: {
  selection: RowSelection;
  noun: string;
  levels: readonly AccessLevel[];
  onApply: (level: AccessLevel) => void | Promise<void>;
  skippedFor?: (level: AccessLevel) => number;
  disabled?: boolean;
}) {
  const actions: BulkAction[] = levels.map((level) => ({
    id: level,
    label: LEVEL_LABELS[level],
    question: (count, plural) => `Set access to ${LEVEL_LABELS[level]} for ${count} ${plural}?`,
    detail: (count) =>
      `Their access changes in one save${level === 'none' ? `: None takes ${count === 1 ? 'it' : 'them'} out` : ''}.`,
    confirm: `Set to ${LEVEL_LABELS[level]}`,
  }));
  return (
    <BulkBar
      selection={selection}
      noun={noun}
      intro="Set access to"
      actions={actions}
      onApply={(id) => onApply(id as AccessLevel)}
      skippedFor={skippedFor ? (id) => skippedFor(id as AccessLevel) : undefined}
      disabled={disabled}
    />
  );
}
