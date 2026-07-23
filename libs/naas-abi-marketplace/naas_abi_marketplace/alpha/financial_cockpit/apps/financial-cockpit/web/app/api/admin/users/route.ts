import { NextResponse } from 'next/server';

import { getSession, isAdminSession } from '@/lib/auth/session';
import { getEntities, getPageLabel } from '@/lib/config/loadConfig';
import {
  getAssignablePages,
  FinanceUserValidationError,
  createUser,
  getAllUsers,
  listAdminUsers,
  loadDatastoreUsers,
} from '@/lib/server/financeUsers';
import type { EntityId, PageId } from '@/lib/types';
import { normalizePageId } from '@/lib/types';

export const dynamic = 'force-dynamic';

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

export async function GET() {
  const { error } = await requireAdminSession();
  if (error) return error;

  const [users, datastoreUsers, entities] = await Promise.all([
    getAllUsers(),
    loadDatastoreUsers(),
    getEntities(),
  ]);
  const adminUsers = listAdminUsers();
  const pages = getAssignablePages().map((pageId) => ({
    page_id: pageId,
    label: getPageLabel(pageId),
  }));

  return NextResponse.json({
    users,
    adminUsers,
    datastoreUsers,
    entities,
    pages,
  });
}

export async function POST(request: Request) {
  const { error } = await requireAdminSession();
  if (error) return error;

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

    const user = await createUser({
      name: asString(body?.name),
      email: asString(body?.email),
      allowed_entities: allowedEntities,
      allowed_pages: allowedPages,
      default_entity_id: defaultEntityId,
    });
    return NextResponse.json({ user }, { status: 201 });
  } catch (err) {
    if (err instanceof FinanceUserValidationError) {
      return NextResponse.json({ error: err.message }, { status: 400 });
    }
    console.error('Failed to create user', err);
    return NextResponse.json({ error: 'La création a échoué.' }, { status: 500 });
  }
}
