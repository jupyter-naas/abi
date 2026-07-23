import { NextResponse } from 'next/server';

import { getSession, isAdminSession } from '@/lib/auth/session';
import {
  FinanceUserValidationError,
  deleteUser,
  updateUser,
} from '@/lib/server/financeUsers';
import type { EntityId, PageId } from '@/lib/types';
import { normalizePageId } from '@/lib/types';

export const dynamic = 'force-dynamic';

type RouteContext = {
  params: Promise<{ userId: string }>;
};

async function requireAdminSession() {
  const session = await getSession();
  if (!session) {
    return { error: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }) };
  }
  if (!(await isAdminSession(session))) {
    return { error: NextResponse.json({ error: 'Forbidden' }, { status: 403 }) };
  }
  return { session };
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

export async function PUT(request: Request, context: RouteContext) {
  const { error } = await requireAdminSession();
  if (error) return error;

  const { userId } = await context.params;

  let body: Record<string, unknown> | null;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: 'Requête invalide' }, { status: 400 });
  }

  try {
    const allowedPages = asStringArray(body?.allowed_pages)
      .map((p) => normalizePageId(p))
      .filter((p): p is PageId => p !== null);
    const allowedEntities = asStringArray(body?.allowed_entities) as EntityId[];
    const defaultEntityId =
      typeof body?.default_entity_id === 'string' && body.default_entity_id.trim()
        ? (body.default_entity_id as EntityId)
        : null;

    const user = await updateUser(userId, {
      name: asString(body?.name),
      email: asString(body?.email),
      allowed_entities: allowedEntities,
      allowed_pages: allowedPages,
      default_entity_id: defaultEntityId,
    });
    if (!user) {
      return NextResponse.json({ error: 'Utilisateur introuvable' }, { status: 404 });
    }
    return NextResponse.json({ user });
  } catch (err) {
    if (err instanceof FinanceUserValidationError) {
      return NextResponse.json({ error: err.message }, { status: 400 });
    }
    console.error('Failed to update user', err);
    return NextResponse.json({ error: 'La mise à jour a échoué.' }, { status: 500 });
  }
}

export async function DELETE(_request: Request, context: RouteContext) {
  const { error } = await requireAdminSession();
  if (error) return error;

  const { userId } = await context.params;

  try {
    const deleted = await deleteUser(userId);
    if (!deleted) {
      return NextResponse.json({ error: 'Utilisateur introuvable' }, { status: 404 });
    }
    return NextResponse.json({ ok: true });
  } catch (err) {
    if (err instanceof FinanceUserValidationError) {
      return NextResponse.json({ error: err.message }, { status: 400 });
    }
    console.error('Failed to delete user', err);
    return NextResponse.json({ error: 'La suppression a échoué.' }, { status: 500 });
  }
}
