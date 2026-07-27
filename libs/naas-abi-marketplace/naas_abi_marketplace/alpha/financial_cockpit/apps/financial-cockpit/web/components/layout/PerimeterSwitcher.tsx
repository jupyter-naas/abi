'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button, Dialog, DialogTrigger, Popover } from 'react-aria-components';

import type { EntityGalleryEntry } from '@/components/gallery/EntityGallery';
import type { EntityConfig } from '@/lib/types';
import { isConsolidation } from '@/lib/config/entityHelpers';
import { sortConsolidations, sortOrganizations } from '@/lib/entitySort';
import { formatEntityName } from '@/lib/format';

type PerimeterSwitcherProps = {
  entries: EntityGalleryEntry[];
  currentEntityId?: string | null;
  placeholder?: string;
};

/**
 * Logo-adjacent perimeter picker: shows the active perimeter (or a placeholder
 * on admin/settings screens) and opens a searchable list grouped by type. Each
 * entry carries its precomputed entry href so selection navigates straight into
 * a page the user can access.
 */
export function PerimeterSwitcher({
  entries,
  currentEntityId = null,
  placeholder = 'Sélectionner un périmètre',
}: PerimeterSwitcherProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const hrefById = useMemo(
    () => new Map(entries.map((entry) => [entry.entity.entity_id, entry.href])),
    [entries],
  );

  const current = entries.find((e) => e.entity.entity_id === currentEntityId) ?? null;
  const label = current ? formatEntityName(current.entity.display_name) : placeholder;

  const normalizedQuery = query.trim().toLowerCase();
  const matches = entries
    .map((entry) => entry.entity)
    .filter((entity) =>
      formatEntityName(entity.display_name).toLowerCase().includes(normalizedQuery),
    );
  const organizations = sortOrganizations(matches.filter((e) => !isConsolidation(e)));
  const consolidations = sortConsolidations(matches.filter((e) => isConsolidation(e)));

  function select(entity: EntityConfig) {
    const href = hrefById.get(entity.entity_id);
    if (!href) return;
    setOpen(false);
    setQuery('');
    router.push(href);
  }

  return (
    <DialogTrigger
      isOpen={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setQuery('');
      }}
    >
      <Button
        aria-label="Changer de périmètre"
        className="group flex min-w-0 flex-1 items-center gap-1.5 rounded-md px-2 py-1 text-left outline-none transition-colors data-[hovered]:bg-[var(--accent)] data-[focus-visible]:ring-2 data-[focus-visible]:ring-inset data-[focus-visible]:ring-secondary"
      >
        <span
          className={`min-w-0 flex-1 truncate text-base font-semibold ${
            current ? 'text-[var(--text)]' : 'text-[var(--text-muted)]'
          }`}
        >
          {label}
        </span>
        <span aria-hidden className="shrink-0 text-[var(--text-muted)]">
          ▾
        </span>
      </Button>
      <Popover
        placement="bottom start"
        className="w-[16rem] max-w-[calc(100vw-1rem)] rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-lg outline-none"
      >
        <Dialog aria-label="Périmètres" className="outline-none">
          <div className="border-b border-[var(--border)] p-2">
            <input
              type="search"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher un périmètre…"
              aria-label="Rechercher un périmètre"
              className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm text-[var(--text)] outline-none transition focus:border-[var(--secondary)]"
            />
          </div>
          <div className="max-h-80 overflow-y-auto p-1.5">
            {organizations.length === 0 && consolidations.length === 0 ? (
              <p className="px-3 py-4 text-center text-sm text-[var(--text-muted)]">
                Aucun périmètre.
              </p>
            ) : null}
            {consolidations.length > 0 ? (
              <Section label="Consolidations">
                {consolidations.map((entity) => (
                  <PerimeterItem
                    key={entity.entity_id}
                    entity={entity}
                    active={entity.entity_id === currentEntityId}
                    onSelect={select}
                  />
                ))}
              </Section>
            ) : null}
            {organizations.length > 0 ? (
              <Section label="Organisations">
                {organizations.map((entity) => (
                  <PerimeterItem
                    key={entity.entity_id}
                    entity={entity}
                    active={entity.entity_id === currentEntityId}
                    onSelect={select}
                  />
                ))}
              </Section>
            ) : null}
          </div>
        </Dialog>
      </Popover>
    </DialogTrigger>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-1 last:mb-0">
      <p className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
        {label}
      </p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function PerimeterItem({
  entity,
  active,
  onSelect,
}: {
  entity: EntityConfig;
  active: boolean;
  onSelect: (entity: EntityConfig) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(entity)}
      className={`block w-full rounded-md px-3 py-2 text-left text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-secondary ${
        active
          ? 'bg-[var(--secondary)] font-semibold text-white'
          : 'text-[var(--text)] hover:bg-[var(--accent)]'
      }`}
      aria-current={active ? 'true' : undefined}
    >
      <span className="block truncate">{formatEntityName(entity.display_name)}</span>
    </button>
  );
}
