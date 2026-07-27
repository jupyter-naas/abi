import { notFound } from 'next/navigation';

import { PerimetersManager } from '@/components/admin/PerimetersManager';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { requireAdmin } from '@/lib/auth/session';
import {
  getEntities,
  isConsolidation,
  resolveEntityEntryPath,
} from '@/lib/config/loadConfig';
import { sortConsolidations, sortOrganizations } from '@/lib/entitySort';
import type { EntityConfig, SessionPayload } from '@/lib/types';

export const dynamic = 'force-dynamic';

function toGalleryEntries(session: SessionPayload, entities: EntityConfig[]) {
  return entities
    .map((entity) => {
      const href = resolveEntityEntryPath(session, entity);
      return href ? { entity, href } : null;
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
}

export default async function AdminPerimetersPage() {
  const session = await requireAdmin().catch(() => notFound());

  const entities = await getEntities();
  const organizations = sortOrganizations(
    entities.filter((entity) => !isConsolidation(entity)),
  );
  const consolidations = sortConsolidations(
    entities.filter((entity) => isConsolidation(entity)),
  );

  return (
    <AdminLayout displayName={session.displayName} active="perimeters">
      <PerimetersManager
        organizations={toGalleryEntries(session, organizations)}
        consolidations={toGalleryEntries(session, consolidations)}
      />
    </AdminLayout>
  );
}
