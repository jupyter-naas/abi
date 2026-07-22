import { redirect } from 'next/navigation';

import { EntityGallery } from '@/components/gallery/EntityGallery';
import { GalleryShell } from '@/components/layout/GalleryShell';
import { getSession, isAdminSession } from '@/lib/auth/session';
import {
  getAllowedEntities,
  getAppConfig,
  getEntityById,
  isConsolidation,
  resolveEntityEntryPath,
} from '@/lib/config/loadConfig';
import { getUserById } from '@/lib/server/financeUsers';
import { ALL_ENTITIES_ENTITY_ID } from '@/lib/entitySort';
import { sortConsolidations, sortOrganizations } from '@/lib/entitySort';
import type { EntityConfig } from '@/lib/types';

export const dynamic = 'force-dynamic';

function toGalleryEntries(
  session: NonNullable<Awaited<ReturnType<typeof getSession>>>,
  entities: EntityConfig[],
) {
  return entities
    .map((entity) => {
      const href = resolveEntityEntryPath(session, entity);
      return href ? { entity, href } : null;
    })
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
}

export default async function HomePage() {
  const session = await getSession();
  if (!session) {
    redirect('/login');
  }

  const isAdmin = await isAdminSession(session);
  const app = getAppConfig();

  // Everyone lands on the configured default perimeter when one is set
  // (app.default_entity in config). Otherwise admins fall back to
  // "Toutes les entités" and standard users to their assigned perimeter.
  const defaultEntityId =
    app.default_entity ??
    (isAdmin
      ? ALL_ENTITIES_ENTITY_ID
      : (await getUserById(session.userId))?.default_entity_id ?? null);
  if (defaultEntityId) {
    const defaultEntity = await getEntityById(defaultEntityId);
    if (defaultEntity) {
      const defaultHref = resolveEntityEntryPath(session, defaultEntity);
      if (defaultHref) {
        redirect(defaultHref);
      }
    }
  }

  if (isAdmin) {
    redirect('/admin');
  }

  const allowed = await getAllowedEntities(session);
  const organizations = sortOrganizations(
    allowed.filter((entity) => !isConsolidation(entity)),
  );
  const consolidations = sortConsolidations(
    allowed.filter((entity) => isConsolidation(entity)),
  );

  return (
    <GalleryShell appName={app.name}>
      <EntityGallery
        organizations={toGalleryEntries(session, organizations)}
        consolidations={toGalleryEntries(session, consolidations)}
      />
    </GalleryShell>
  );
}
