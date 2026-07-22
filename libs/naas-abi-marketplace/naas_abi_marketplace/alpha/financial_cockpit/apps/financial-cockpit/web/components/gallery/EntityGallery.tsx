'use client';

import { useState } from 'react';
import { Button, Link } from 'react-aria-components';

import type { EntityConfig } from '@/lib/types';
import { formatEntityName } from '@/lib/format';
import { galleryCard } from '@/lib/ariaStyles';

export type EntityGalleryEntry = {
  entity: EntityConfig;
  href: string;
};

type EntityGalleryProps = {
  organizations: EntityGalleryEntry[];
  consolidations: EntityGalleryEntry[];
  /** Drop max-width centering so the grid fills the parent (admin layout). */
  fullWidth?: boolean;
  /** Cards per row at large breakpoints. Default 3 (home); admin uses 4. */
  columns?: 3 | 4;
  /** Intro subtitle above the sections. Default true; admin hides it when rendered outside. */
  showIntro?: boolean;
};

export function EntityGallery({
  organizations,
  consolidations,
  fullWidth = false,
  columns = 3,
  showIntro = true,
}: EntityGalleryProps) {
  const hasEntries = organizations.length > 0 || consolidations.length > 0;
  const shellClass = fullWidth ? 'w-full' : 'mx-auto w-full max-w-6xl';

  return (
    <div className={shellClass}>
      {showIntro ? (
        <header className="mb-8 sm:mb-10">
          <p className="type-subtitle m-0">
            Choisissez une consolidation ou une société pour accéder au reporting.
          </p>
        </header>
      ) : null}

      {!hasEntries ? (
        <p className="text-sm text-[var(--text-muted)]">
          Aucun périmètre disponible pour votre compte.
        </p>
      ) : null}

      {consolidations.length > 0 ? (
        <GallerySection title="Consolidations" count={consolidations.length} columns={columns}>
          {consolidations.map(({ entity, href }) => (
            <ConsolidationCard key={entity.entity_id} entity={entity} href={href} />
          ))}
        </GallerySection>
      ) : null}

      {organizations.length > 0 ? (
        <GallerySection
          title="Sociétés"
          count={organizations.length}
          columns={columns}
          className={consolidations.length > 0 ? 'mt-10' : undefined}
        >
          {organizations.map(({ entity, href }) => (
            <OrganizationCard key={entity.entity_id} entity={entity} href={href} />
          ))}
        </GallerySection>
      ) : null}
    </div>
  );
}

function GallerySection({
  title,
  count,
  columns,
  className = '',
  children,
}: {
  title: string;
  count: number;
  columns: 3 | 4;
  className?: string;
  children: React.ReactNode;
}) {
  const gridCols =
    columns === 4
      ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4'
      : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4';

  return (
    <section className={className}>
      <div className="flex items-baseline gap-2 mb-4">
        <h2 className="type-title-3 m-0">{title}</h2>
        <span className="text-xs font-medium text-[var(--text-muted)]">{count}</span>
      </div>
      <div className={gridCols}>{children}</div>
    </section>
  );
}

const cardTitle =
  'font-semibold text-sm sm:text-base leading-snug break-words text-center text-[var(--text)]';

function OrganizationCard({ entity, href }: { entity: EntityConfig; href: string }) {
  return (
    <Link
      href={href}
      className={`${galleryCard} flex min-h-[5.5rem] items-center justify-center px-4 py-5`}
    >
      <span className={cardTitle}>{formatEntityName(entity.display_name)}</span>
    </Link>
  );
}

function ConsolidationCard({ entity, href }: { entity: EntityConfig; href: string }) {
  const [expanded, setExpanded] = useState(false);
  const companies = [...(entity.companies ?? [])].sort((a, b) =>
    a.display_name.localeCompare(b.display_name, 'fr', { sensitivity: 'base' }),
  );

  return (
    <div className={`${galleryCard} flex flex-col items-center px-4 py-5`}>
      <Link href={href} className={`${cardTitle} w-full hover:opacity-90 transition-opacity`}>
        {formatEntityName(entity.display_name)}
      </Link>

      {companies.length > 0 ? (
        <div className="mt-3 w-full">
          <Button
            type="button"
            onPress={() => setExpanded((open) => !open)}
            aria-expanded={expanded}
            className="mx-auto flex items-center gap-1.5 text-xs font-medium text-secondary outline-none data-[focus-visible]:ring-2 data-[focus-visible]:ring-secondary rounded px-2 py-1"
          >
            {companies.length} société{companies.length > 1 ? 's' : ''}
            <span aria-hidden className="text-[10px]">
              {expanded ? '▴' : '▾'}
            </span>
          </Button>

          {expanded ? (
            <ul className="mt-3 w-full border-t border-[var(--border)] pt-3 space-y-1.5 text-left">
              {companies.map((company) => (
                <li
                  key={company.organization_slug}
                  className="text-xs text-[var(--text-muted)] truncate"
                >
                  {formatEntityName(company.display_name)}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
