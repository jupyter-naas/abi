import { notFound, redirect } from 'next/navigation';

import { canAccessThemePage } from '@/lib/config/loadConfig';
import { getSession, isAdminSession } from '@/lib/auth/session';

export const dynamic = 'force-dynamic';

/** Theme is admin-only; keep /theme as a stable URL that redirects into admin chrome. */
export default async function ThemePage() {
  const session = await getSession();
  if (!session) {
    redirect('/login');
  }

  if (!canAccessThemePage(session) || !(await isAdminSession(session))) {
    notFound();
  }

  redirect('/admin/theme');
}
