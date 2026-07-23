import { NextResponse } from 'next/server';

import { getSession, requireThemePageAccess } from '@/lib/auth/session';
import {
  loadThemeConfig,
  normalizeThemeConfig,
  writeThemeConfig,
  type ThemeConfigFile,
} from '@/lib/theme/themeConfig';

export const dynamic = 'force-dynamic';

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Non autorisé' }, { status: 401 });
  }

  return NextResponse.json(loadThemeConfig());
}

export async function PUT(request: Request) {
  try {
    await requireThemePageAccess();
  } catch {
    return NextResponse.json({ error: 'Accès refusé' }, { status: 403 });
  }

  let body: Partial<ThemeConfigFile>;
  try {
    body = (await request.json()) as Partial<ThemeConfigFile>;
  } catch {
    return NextResponse.json({ error: 'Requête invalide' }, { status: 400 });
  }

  const current = loadThemeConfig();
  const saved = writeThemeConfig(normalizeThemeConfig({ ...current, ...body }));

  return NextResponse.json(saved);
}
