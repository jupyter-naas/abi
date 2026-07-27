import { notFound, redirect } from 'next/navigation';

import {
  canAccess,
  getAllowedPages,
  getAppConfig,
  getEntity,
} from '@/lib/config/loadConfig';
import { getSession } from '@/lib/auth/session';

export const dynamic = 'force-dynamic';

type Props = {
  params: Promise<{ entitySlug: string }>;
};

export default async function EntityIndexPage({ params }: Props) {
  const { entitySlug } = await params;
  const session = await getSession();
  if (!session) {
    redirect('/login');
  }

  const entity = await getEntity(entitySlug);
  if (!entity) {
    notFound();
  }

  const defaultPage = getAppConfig().default_page;
  const entityPages = getAllowedPages(session, entity.entity_id).filter(
    (pageId) => pageId !== 'theme',
  );

  const pageId =
    defaultPage !== 'theme' && entityPages.includes(defaultPage)
      ? defaultPage
      : entityPages[0];

  if (!pageId || !canAccess(session, entity.entity_id, pageId)) {
    notFound();
  }

  redirect(`/${entitySlug}/${pageId}`);
}
