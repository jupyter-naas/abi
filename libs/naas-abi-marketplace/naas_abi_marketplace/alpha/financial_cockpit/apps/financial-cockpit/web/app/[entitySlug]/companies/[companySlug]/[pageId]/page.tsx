import { redirect } from 'next/navigation';

import { entityPageHref } from '@/lib/routes';

export const dynamic = 'force-dynamic';

type Props = {
  params: Promise<{ entitySlug: string; companySlug: string; pageId: string }>;
  searchParams?: Promise<{ scenario?: string }>;
};

/**
 * Legacy path `/…/companies/{company}/{page}` → canonical
 * `/…/{page}?company=…&scenario=…`.
 */
export default async function LegacyCompanyPage({ params, searchParams }: Props) {
  const { entitySlug, companySlug, pageId } = await params;
  const resolvedSearch = searchParams ? await searchParams : {};
  redirect(
    entityPageHref(
      entitySlug,
      pageId,
      companySlug,
      null,
      resolvedSearch.scenario ?? null,
    ),
  );
}
