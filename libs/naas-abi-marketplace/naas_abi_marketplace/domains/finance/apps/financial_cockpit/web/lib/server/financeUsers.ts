import 'server-only';

import { readJsonFile, writeJsonFile } from '@/lib/data/storage';
import { getEnabledPages, getEntities, loadConfig } from '@/lib/config/loadConfig';
import type { EntityId, PageId, UserConfig } from '@/lib/types';
import { normalizePageId } from '@/lib/types';

/**
 * App-managed users (added/edited/removed from /admin/users): `admin`-role users
 * (full access to every app) and role-less viewers (scoped to their allowed
 * entities/pages). The `owner` lives in config.yaml and is the read-only
 * exception — see the `users:` comment there. This datastore file is merged with
 * the config owner at lookup time.
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
  // Admins have full, unscoped access — entity/page grants don't apply, so an
  // empty scope is expected and must not drop them.
  if (user.role === 'admin') {
    return {
      ...user,
      role: 'admin',
      allowed_entities: [],
      allowed_pages: [],
      default_entity_id: null,
    };
  }

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

/** Datastore users: UI-managed admins (full access) and scoped viewers. */
export async function loadDatastoreUsers(): Promise<UserConfig[]> {
  const entities = await getEntities();
  const validEntityIds = new Set(entities.map((entity) => entity.entity_id));
  return (await readUsersFile()).records
    .map((user) => sanitizeUserEntities(user, validEntityIds))
    .filter((user): user is UserConfig => user !== null);
}

/** Config.yaml users — the owner role, the only one that still lives there. */
export function listConfigUsers(): UserConfig[] {
  return loadConfig().users ?? [];
}

/**
 * Read-only, config-managed users the app never edits or writes to the
 * datastore: the owner(s) from config.yaml. Shown in the user manager as
 * read-only. (Admins are datastore-managed and fully editable.)
 */
export function listProtectedUsers(): UserConfig[] {
  return listConfigUsers();
}

/** True for a protected user (the owner) — never editable from the app. */
export function isProtectedUser(userId: string): boolean {
  return listProtectedUsers().some((u) => u.user_id === userId);
}

/**
 * Full login allowlist: protected users (the owner) merged with the datastore
 * (UI-managed admins & viewers). A datastore record supersedes a protected user
 * sharing its user_id or email, so the merge never double-counts. Read-only:
 * nothing is written here.
 */
export async function getAllUsers(): Promise<UserConfig[]> {
  const datastore = await loadDatastoreUsers();
  const takenIds = new Set(datastore.map((u) => u.user_id));
  const takenEmails = new Set(datastore.map((u) => u.email.toLowerCase()));
  const protectedUsers = listProtectedUsers().filter(
    (u) => !takenIds.has(u.user_id) && !takenEmails.has(u.email.toLowerCase()),
  );
  return [...protectedUsers, ...datastore];
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

export type FinanceUserInput = {
  name: string;
  email: string;
  /** `admin` grants full access; omit/null for a scoped viewer. */
  role?: 'admin' | null;
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
  role: 'admin' | null;
  allowed_entities: EntityId[];
  allowed_pages: PageId[];
  default_entity_id: EntityId | null;
}> {
  const name = input.name.trim();
  const email = input.email.trim().toLowerCase();
  const role = input.role === 'admin' ? 'admin' : null;

  if (!name) {
    throw new FinanceUserValidationError('Le nom est requis.');
  }
  if (!EMAIL_RE.test(email)) {
    throw new FinanceUserValidationError('Adresse e-mail invalide.');
  }

  const clashEmail = await getUserByEmail(email);
  if (clashEmail && clashEmail.user_id !== existingUserId) {
    throw new FinanceUserValidationError('This e-mail address is already in use.');
  }

  // Admins have full, unscoped access: no entity/page selection required.
  if (role === 'admin') {
    return {
      name,
      email,
      role: 'admin',
      allowed_entities: [],
      allowed_pages: [],
      default_entity_id: null,
    };
  }

  const entities = await getEntities();
  const entityIds = new Set(entities.map((e) => e.entity_id));
  const allowedEntities = [...new Set(input.allowed_entities.map((id) => id.trim()).filter(Boolean))];
  for (const id of allowedEntities) {
    if (!entityIds.has(id)) {
      throw new FinanceUserValidationError(`Unknown perimeter: ${id}.`);
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
    throw new FinanceUserValidationError('Select at least one page.');
  }
  if (allowedEntities.length === 0) {
    throw new FinanceUserValidationError('Select at least one perimeter.');
  }

  const rawDefault = input.default_entity_id?.trim() || null;
  if (rawDefault && !allowedEntities.includes(rawDefault)) {
    throw new FinanceUserValidationError(
      'The default perimeter must be one of the allowed perimeters.',
    );
  }
  const defaultEntityId = rawDefault;

  return {
    name,
    email,
    role: null,
    allowed_entities: allowedEntities,
    allowed_pages: allowedPages,
    default_entity_id: defaultEntityId,
  };
}

/** Build a datastore record from validated input, omitting empty scope fields. */
function toUserRecord(
  userId: string,
  valid: {
    name: string;
    email: string;
    role: 'admin' | null;
    allowed_entities: EntityId[];
    allowed_pages: PageId[];
    default_entity_id: EntityId | null;
  },
): UserConfig {
  if (valid.role === 'admin') {
    return { user_id: userId, name: valid.name, email: valid.email, role: 'admin' };
  }
  return {
    user_id: userId,
    name: valid.name,
    email: valid.email,
    allowed_entities: valid.allowed_entities,
    allowed_pages: valid.allowed_pages,
    default_entity_id: valid.default_entity_id,
  };
}

export async function createUser(input: FinanceUserInput): Promise<UserConfig> {
  const valid = await assertValid(input, null);
  const record = toUserRecord(crypto.randomUUID(), valid);

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
  if (isProtectedUser(userId)) {
    throw new FinanceUserValidationError(
      'This user is managed in the configuration and cannot be edited from the app.',
    );
  }

  const records = await loadDatastoreUsers();
  const index = records.findIndex((u) => u.user_id === userId);
  if (index === -1) {
    return null;
  }

  const valid = await assertValid(input, userId);
  // Rebuild from scratch so a role change clears the fields the other role
  // doesn't use (e.g. promoting a viewer drops its entity/page scope).
  const updated = toUserRecord(userId, valid);

  const next = [...records];
  next[index] = updated;
  const written = await writeUsersFile(next);
  if (!written) {
    throw new Error('Failed to persist the updated user');
  }
  return updated;
}

export async function deleteUser(userId: string): Promise<boolean> {
  if (isProtectedUser(userId)) {
    throw new FinanceUserValidationError(
      'This user is managed in the configuration and cannot be deleted from the app.',
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
