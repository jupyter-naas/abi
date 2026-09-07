'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';

import {
  EntityGallery,
  type EntityGalleryEntry,
} from '@/components/gallery/EntityGallery';
import { ViewToggle, type ViewMode } from '@/components/admin/ViewToggle';
import {
  DataTable,
  type DataTableColumn,
} from '@/components/dashboard/table/DataTable';
import { formatEntityName } from '@/lib/format';
import type { EntityConfig } from '@/lib/types';

type PerimetersManagerProps = {
  organizations: EntityGalleryEntry[];
  consolidations: EntityGalleryEntry[];
};

export function PerimetersManager({
  organizations,
  consolidations,
}: PerimetersManagerProps) {
  const [view, setView] = useState<ViewMode>('gallery');

  const tableRecords = useMemo(() => {
    const rows: Record<string, unknown>[] = [];
    for (const { entity, href } of consolidations) {
      rows.push(toRow(entity, href, 'Consolidation'));
    }
    for (const { entity, href } of organizations) {
      rows.push(toRow(entity, href, 'Company'));
    }
    return rows;
  }, [organizations, consolidations]);

  const columns: DataTableColumn[] = useMemo(
    () => [
      {
        key: 'display_name',
        label: 'Name',
        renderValue: (value, record) => (
          <Link
            href={String(record.href)}
            className="font-medium text-[var(--secondary)] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-secondary"
          >
            {formatEntityName(String(value ?? ''))}
          </Link>
        ),
      },
      { key: 'type_label', label: 'Type' },
      { key: 'url_slug', label: 'Slug' },
      { key: 'entity_id', label: 'ID' },
    ],
    [],
  );

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <p className="m-0 text-sm text-[var(--text-muted)]">
          {formatCount(consolidations.length, 'consolidation', 'consolidations')}
          {' · '}
          {formatCount(organizations.length, 'organization', 'organizations')}
        </p>
        <div className="flex items-center justify-start">
          <ViewToggle value={view} onChange={setView} />
        </div>
      </div>

      <p className="type-subtitle m-0">
        Choose a consolidation or a company to open its reporting.
      </p>

      {view === 'gallery' ? (
        <EntityGallery
          organizations={organizations}
          consolidations={consolidations}
          fullWidth
          columns={4}
          showIntro={false}
        />
      ) : (
        <DataTable
          records={tableRecords}
          columns={columns}
          emptyMessage="No perimeter available."
          exportable={false}
          defaultPageSize={20}
        />
      )}
    </div>
  );
}

function toRow(
  entity: EntityConfig,
  href: string,
  typeLabel: string,
): Record<string, unknown> {
  return {
    entity_id: entity.entity_id,
    display_name: entity.display_name,
    url_slug: entity.url_slug,
    type_label: typeLabel,
    href,
  };
}

function formatCount(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
