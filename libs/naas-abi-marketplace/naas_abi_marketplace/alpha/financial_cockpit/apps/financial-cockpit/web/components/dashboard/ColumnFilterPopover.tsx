'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button as RACButton, DialogTrigger, Input, Label, Popover } from 'react-aria-components';

import { Button } from '@/components/ui/Button';
import { fieldInput, popover } from '@/lib/ariaStyles';
import {
  NO_MATCH_COLUMN_FILTER,
  collectUniqueColumnValues,
  formatFilterChipLabel,
  parseColumnFilter,
  serializeColumnFilter,
} from '@/lib/table/columnFilterUtils';

type ColumnFilterPopoverProps = {
  columnKey: string;
  label: string;
  records: Record<string, unknown>[];
  value: string;
  active: boolean;
  onChange: (value: string) => void;
  onClear: () => void;
};

export function formatColumnFilterChipLabel(serialized: string): string {
  return formatFilterChipLabel(serialized);
}

export function ColumnFilterPopover({
  columnKey,
  label,
  records,
  value,
  active,
  onChange,
  onClear,
}: ColumnFilterPopoverProps) {
  const allOptions = useMemo(
    () => collectUniqueColumnValues(records, columnKey),
    [records, columnKey],
  );

  const [search, setSearch] = useState('');
  const [draftSelection, setDraftSelection] = useState<Set<string>>(new Set());
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const selected = parseColumnFilter(value);
    setDraftSelection(new Set(selected ?? allOptions));
    setSearch('');
  }, [isOpen, value, allOptions]);

  const visibleOptions = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return allOptions;
    }
    return allOptions.filter((option) => option.toLowerCase().includes(query));
  }, [allOptions, search]);

  const allVisibleSelected =
    visibleOptions.length > 0 &&
    visibleOptions.every((option) => draftSelection.has(option));
  const someVisibleSelected = visibleOptions.some((option) =>
    draftSelection.has(option),
  );

  function toggleOption(option: string, checked: boolean) {
    setDraftSelection((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(option);
      } else {
        next.delete(option);
      }
      return next;
    });
  }

  function toggleVisibleOptions(checked: boolean) {
    setDraftSelection((current) => {
      const next = new Set(current);
      for (const option of visibleOptions) {
        if (checked) {
          next.add(option);
        } else {
          next.delete(option);
        }
      }
      return next;
    });
  }

  function applyFilter() {
    if (draftSelection.size === 0) {
      onChange(NO_MATCH_COLUMN_FILTER);
      setIsOpen(false);
      return;
    }
    if (draftSelection.size >= allOptions.length) {
      onClear();
      setIsOpen(false);
      return;
    }
    onChange(serializeColumnFilter(draftSelection));
    setIsOpen(false);
  }

  return (
    <DialogTrigger isOpen={isOpen} onOpenChange={setIsOpen}>
      <RACButton
        className={`flex shrink-0 items-center border-l border-white/25 px-2 py-2 transition-colors hover:bg-white/10 outline-none data-[focus-visible]:ring-2 data-[focus-visible]:ring-inset data-[focus-visible]:ring-white/50 ${
          active ? 'bg-white/15 text-white' : 'text-white/70'
        }`}
        aria-label={`Filtrer ${label}`}
        data-filter-trigger=""
      >
        <span className="text-[11px] font-bold" aria-hidden>
          ⎚
        </span>
      </RACButton>
      <Popover
        className={`${popover} w-72 p-0`}
        data-testid={`column-filter-${columnKey}`}
        offset={4}
      >
        <div className="flex max-h-80 flex-col">
          <div className="space-y-2 border-b border-[var(--border)] p-3">
            <Label className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Filtrer — {label}
            </Label>
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Rechercher…"
              className={`${fieldInput} !min-h-9 py-1.5 text-sm`}
              autoFocus
            />
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {allOptions.length === 0 ? (
              <p className="px-2 py-3 text-sm text-[var(--text-muted)]">Aucune valeur.</p>
            ) : (
              <>
                <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--accent)]">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-[var(--border)] accent-[var(--secondary)]"
                    checked={allVisibleSelected}
                    ref={(element) => {
                      if (element) {
                        element.indeterminate =
                          someVisibleSelected && !allVisibleSelected;
                      }
                    }}
                    onChange={(event) => toggleVisibleOptions(event.target.checked)}
                  />
                  <span className="font-medium text-[var(--text)]">
                    {search.trim() ? 'Tout sélectionner (résultats)' : 'Tout sélectionner'}
                  </span>
                </label>

                <div className="my-1 border-t border-[var(--border)]" />

                {visibleOptions.length === 0 ? (
                  <p className="px-2 py-2 text-sm text-[var(--text-muted)]">
                    Aucun résultat pour cette recherche.
                  </p>
                ) : (
                  visibleOptions.map((option) => (
                    <label
                      key={option}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--accent)]"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-[var(--border)] accent-[var(--secondary)]"
                        checked={draftSelection.has(option)}
                        onChange={(event) => toggleOption(option, event.target.checked)}
                      />
                      <span className="truncate text-[var(--text)]" title={option}>
                        {option}
                      </span>
                    </label>
                  ))
                )}
              </>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-[var(--border)] p-3">
            <Button
              variant="ghost"
              onPress={() => {
                onClear();
                setIsOpen(false);
              }}
              className="!w-auto !min-h-9 px-3 py-2 text-xs"
            >
              Effacer
            </Button>
            <Button onPress={applyFilter} className="!w-auto !min-h-9 px-3 py-2 text-xs">
              Appliquer
            </Button>
          </div>
        </div>
      </Popover>
    </DialogTrigger>
  );
}

export function isColumnFilterActive(
  serialized: string,
  records: Record<string, unknown>[],
  columnKey: string,
): boolean {
  if (!serialized.trim()) {
    return false;
  }
  if (serialized === NO_MATCH_COLUMN_FILTER) {
    return true;
  }
  const allOptions = collectUniqueColumnValues(records, columnKey);
  const selected = parseColumnFilter(serialized);
  if (!selected) {
    return false;
  }
  return selected.length > 0 && selected.length < allOptions.length;
}
