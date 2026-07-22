'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button as RACButton, DialogTrigger, Input, Label, Popover } from 'react-aria-components';

import { Button } from '@/components/ui/Button';
import { fieldInput, popover } from '@/lib/ariaStyles';

type Categorie3FilterProps = {
  options: string[];
  selected: ReadonlySet<string>;
  onChange: (selected: Set<string>) => void;
};

/** Multi-select popover filtering the P&L statement by Catégorie 3 (site/tiers). */
export function Categorie3Filter({ options, selected, onChange }: Categorie3FilterProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [draft, setDraft] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setDraft(new Set(selected));
    setSearch('');
  }, [isOpen, selected]);

  const visibleOptions = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return options;
    }
    return options.filter((option) => option.toLowerCase().includes(query));
  }, [options, search]);

  function toggle(option: string, checked: boolean) {
    setDraft((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(option);
      } else {
        next.delete(option);
      }
      return next;
    });
  }

  const active = selected.size > 0;
  const label =
    selected.size === 0
      ? 'Catégorie 3 : toutes'
      : selected.size === 1
        ? `Catégorie 3 : ${[...selected][0]}`
        : `Catégorie 3 : ${selected.size} sélectionnées`;

  return (
    <DialogTrigger isOpen={isOpen} onOpenChange={setIsOpen}>
      <RACButton
        className={`flex min-h-11 items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium outline-none transition-colors ${
          active
            ? 'border-[var(--secondary)] bg-[color-mix(in_srgb,var(--secondary)_12%,var(--surface))] text-[var(--text)]'
            : 'border-[var(--border)] bg-[var(--accent)] text-[var(--text)]'
        } data-[focus-visible]:ring-2 data-[focus-visible]:ring-secondary data-[pressed]:bg-[var(--surface)]`}
      >
        <span className="truncate">{label}</span>
      </RACButton>
      <Popover className={`${popover} w-72 p-0`} offset={4}>
        <div className="flex max-h-80 flex-col">
          <div className="space-y-2 border-b border-[var(--border)] p-3">
            <Label className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              Filtrer par Catégorie 3
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
            {visibleOptions.length === 0 ? (
              <p className="px-2 py-3 text-sm text-[var(--text-muted)]">Aucune valeur.</p>
            ) : (
              visibleOptions.map((option) => (
                <label
                  key={option}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--accent)]"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-[var(--border)] accent-[var(--secondary)]"
                    checked={draft.has(option)}
                    onChange={(event) => toggle(option, event.target.checked)}
                  />
                  <span className="truncate text-[var(--text)]" title={option}>
                    {option}
                  </span>
                </label>
              ))
            )}
          </div>
          <div className="flex justify-end gap-2 border-t border-[var(--border)] p-3">
            <Button
              variant="ghost"
              onPress={() => {
                onChange(new Set());
                setIsOpen(false);
              }}
              className="!w-auto !min-h-9 px-3 py-2 text-xs"
            >
              Effacer
            </Button>
            <Button
              onPress={() => {
                onChange(draft);
                setIsOpen(false);
              }}
              className="!w-auto !min-h-9 px-3 py-2 text-xs"
            >
              Appliquer
            </Button>
          </div>
        </div>
      </Popover>
    </DialogTrigger>
  );
}
