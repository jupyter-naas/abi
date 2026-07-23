import 'server-only';

import { readJsonFile, writeJsonFile } from '@/lib/data/storage';
import { getEnabledPages, getEntities, loadConfig } from '@/lib/config/loadConfig';
import type { EntityId, PageId, UserConfig } from '@/lib/types';
import { normalizePageId } from '@/lib/types';

/**
 * Non-admin users, app-managed (added/edited/removed from /admin/users).
 * Admin-role users stay hand-maintained in config.yaml — see the `users:`
 * comment there. This file is merged with config.yaml's admins at lookup time.
 *
 * Key uses plural `globals/` to match `globals/entities.json`.
 */
const USERS_KEY = 'globals/users.json';

/**
 * Pages that can be granted to standard users.
 * Theme stays admin-only; every other enabled page from config is assignable.
 */
export function getAssignablePages(): PageId[] {
  return getEnabledPages().filter((pageId) => pageId !== 'theme');
}

/** Retired perimeter ids kept out of login and admin UI. */
const LEGACY_ENTITY_IDS = new Set<EntityId>(['property_management']);

type UsersFile = {
  schema_version: string;
  updated_at: string | null;
  records: UserConfig[];
};

async function readUsersFile(): Promise<UsersFile> {
  const parsed = await readJsonFile<Partial<UsersFile>>(USERS_KEY);
  if (!parsed) {
    return { schema_version: '1.0', updated_at: null, records: [] };
  }
  return {
    schema_version: parsed.schema_version ?? '1.0',
    updated_at: parsed.updated_at ?? null,
    records: Array.isArray(parsed.records) ? parsed.records : [],
  };
}

async function writeUsersFile(records: UserConfig[]): Promise<boolean> {
  const file: UsersFile = {
    schema_version: '1.0',
    updated_at: new Date().toISOString(),
    records,
  };
  return writeJsonFile(USERS_KEY, file);
}

function sanitizeUserEntities(
  user: UserConfig,
  validEntityIds: ReadonlySet<EntityId>,
): UserConfig | null {
  const allowed_entities = (user.allowed_entities ?? []).filter(
    (id) => validEntityIds.has(id) && !LEGACY_ENTITY_IDS.has(id),
  );
  if (allowed_entities.length === 0) {
    return null;
  }

  const default_entity_id =
    user.default_entity_id && allowed_entities.includes(user.default_entity_id)
      ? user.default_entity_id
      : allowed_entities[0];

  return {
    ...user,
    allowed_entities,
    allowed_pages: (user.allowed_pages ?? [])
      .map((pageId) => normalizePageId(pageId))
      .filter((pageId): pageId is PageId => pageId !== null),
    default_entity_id,
  };
}

/** All non-admin users from the datastore. */
export async function loadDatastoreUsers(): Promise<UserConfig[]> {
  const entities = await getEntities();
  const validEntityIds = new Set(entities.map((entity) => entity.entity_id));
  return (await readUsersFile()).records
    .map((user) => sanitizeUserEntities(user, validEntityIds))
    .filter((user): user is UserConfig => user !== null);
}

/** Admin-role users from config.yaml — the only role that still lives there. */
export function listAdminUsers(): UserConfig[] {
  return (loadConfig().users ?? []).filter((u) => u.role === 'admin');
}

/** Admins (config.yaml) + standard users (datastore) — the full login allowlist. */
export async function getAllUsers(): Promise<UserConfig[]> {
  return [...listAdminUsers(), ...(await loadDatastoreUsers())];
}

export async function getUserById(userId: string): Promise<UserConfig | null> {
  return (await getAllUsers()).find((u) => u.user_id === userId) ?? null;
}

export async function getUserByEmail(email: string): Promise<UserConfig | null> {
  const normalized = email.trim().toLowerCase();
  return (
    (await getAllUsers()).find((u) => u.email.toLowerCase() === normalized) ?? null
  );
}

export function isConfigAdmin(userId: string): boolean {
  return listAdminUsers().some((u) => u.user_id === userId);
}

export type FinanceUserInput = {
  name: string;
  email: string;
  allowed_entities: EntityId[];
  allowed_pages: PageId[];
  default_entity_id?: EntityId | null;
};

export class FinanceUserValidationError extends Error {}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function assertValid(
  input: FinanceUserInput,
  existingUserId: string | null,
): Promise<{
  name: string;
  email: string;
  allowed_entities: EntityId[];
  allowed_pages: PageId[];
  default_entity_id: EntityId | null;
}> {
  const name = input.name.trim();
  const email = input.email.trim().toLowerCase();

  if (!name) {
    throw new FinanceUserValidationError('Le nom est requis.');
  }
  if (!EMAIL_RE.test(email)) {
    throw new FinanceUserValidationError('Adresse e-mail invalide.');
  }

  const entities = await getEntities();
  const entityIds = new Set(entities.map((e) => e.entity_id));
  const allowedEntities = [...new Set(input.allowed_entities.map((id) => id.trim()).filter(Boolean))];
  for (const id of allowedEntities) {
    if (!entityIds.has(id)) {
      throw new FinanceUserValidationError(`Périmètre inconnu : ${id}.`);
    }
  }

  const assignablePages = new Set(getAssignablePages());
  const allowedPages = [
    ...new Set(
      input.allowed_pages
        .map((p) => normalizePageId(p.trim()))
        .filter((p): p is PageId => p !== null && assignablePages.has(p)),
    ),
  ];
  if (allowedPages.length === 0) {
    throw new FinanceUserValidationError('Sélectionnez au moins une page.');
  }
  if (allowedEntities.length === 0) {
    throw new FinanceUserValidationError('Sélectionnez au moins un périmètre.');
  }

  const rawDefault = input.default_entity_id?.trim() || null;
  if (rawDefault && !allowedEntities.includes(rawDefault)) {
    throw new FinanceUserValidationError(
      'Le périmètre par défaut doit faire partie des périmètres autorisés.',
    );
  }
  const defaultEntityId = rawDefault;

  const clash = await getUserByEmail(email);
  if (clash && clash.user_id !== existingUserId) {
    throw new FinanceUserValidationError('Cette adresse e-mail est déjà utilisée.');
  }

  return {
    name,
    email,
    allowed_entities: allowedEntities,
    allowed_pages: allowedPages,
    default_entity_id: defaultEntityId,
  };
}

export async function createUser(input: FinanceUserInput): Promise<UserConfig> {
  const valid = await assertValid(input, null);
  const record: UserConfig = {
    user_id: crypto.randomUUID(),
    name: valid.name,
    email: valid.email,
    allowed_entities: valid.allowed_entities,
    allowed_pages: valid.allowed_pages,
    default_entity_id: valid.default_entity_id,
  };

  const records = await loadDatastoreUsers();
  const written = await writeUsersFile([...records, record]);
  if (!written) {
    throw new Error('Failed to persist the new user');
  }
  return record;
}

export async function updateUser(
  userId: string,
  input: FinanceUserInput,
): Promise<UserConfig | null> {
  if (isConfigAdmin(userId)) {
    throw new FinanceUserValidationError(
      'Les administrateurs se gèrent dans config.yaml.',
    );
  }

  const records = await loadDatastoreUsers();
  const index = records.findIndex((u) => u.user_id === userId);
  if (index === -1) {
    return null;
  }

  const valid = await assertValid(input, userId);
  const updated: UserConfig = {
    ...records[index],
    name: valid.name,
    email: valid.email,
    allowed_entities: valid.allowed_entities,
    allowed_pages: valid.allowed_pages,
    default_entity_id: valid.default_entity_id,
  };

  const next = [...records];
  next[index] = updated;
  const written = await writeUsersFile(next);
  if (!written) {
    throw new Error('Failed to persist the updated user');
  }
  return updated;
}

export async function deleteUser(userId: string): Promise<boolean> {
  if (isConfigAdmin(userId)) {
    throw new FinanceUserValidationError(
      'Les administrateurs se gèrent dans config.yaml.',
    );
  }

  const records = await loadDatastoreUsers();
  const next = records.filter((u) => u.user_id !== userId);
  if (next.length === records.length) {
    return false;
  }
  const written = await writeUsersFile(next);
  if (!written) {
    throw new Error('Failed to persist the user deletion');
  }
  return true;
}
