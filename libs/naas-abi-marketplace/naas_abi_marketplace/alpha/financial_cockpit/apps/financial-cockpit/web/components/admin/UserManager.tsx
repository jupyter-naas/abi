'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  DataTable,
  type DataTableColumn,
} from '@/components/dashboard/DataTable';
import { ViewToggle, type ViewMode } from '@/components/admin/ViewToggle';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/TextField';
import { galleryCard } from '@/lib/ariaStyles';
import type { EntityConfig, EntityId, PageId, UserConfig } from '@/lib/types';

type PageOption = { page_id: PageId; label: string };

type UserManagerProps = {
  adminUsers: UserConfig[];
  initialUsers: UserConfig[];
  entities: EntityConfig[];
  pages: PageOption[];
};

type FormValues = {
  name: string;
  email: string;
  allowed_entities: EntityId[];
  allowed_pages: PageId[];
  default_entity_id: EntityId | null;
};

type ModalState =
  | { mode: 'create' }
  | { mode: 'edit'; user: UserConfig }
  | null;

const EMPTY_FORM: FormValues = {
  name: '',
  email: '',
  allowed_entities: [],
  allowed_pages: [],
  default_entity_id: null,
};

function userInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return `${parts[0].slice(0, 1)}${parts[parts.length - 1].slice(0, 1)}`.toUpperCase();
}

export function UserManager({
  adminUsers,
  initialUsers,
  entities,
  pages,
}: UserManagerProps) {
  const router = useRouter();
  const [users, setUsers] = useState<UserConfig[]>(initialUsers);
  const [view, setView] = useState<ViewMode>('table');
  const [modal, setModal] = useState<ModalState>(null);
  const [form, setForm] = useState<FormValues>(EMPTY_FORM);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [confirmUser, setConfirmUser] = useState<UserConfig | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState('');

  const adminIds = useMemo(
    () => new Set(adminUsers.map((u) => u.user_id)),
    [adminUsers],
  );

  const allUsers = useMemo(() => [...adminUsers, ...users], [adminUsers, users]);

  const entityNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const entity of entities) {
      map.set(entity.entity_id, entity.display_name);
    }
    return map;
  }, [entities]);

  const pageLabelById = useMemo(() => {
    const map = new Map<string, string>();
    for (const page of pages) {
      map.set(page.page_id, page.label);
    }
    return map;
  }, [pages]);

  const records = useMemo(
    () =>
      allUsers.map((user) => ({
        user_id: user.user_id,
        name: user.name,
        email: user.email,
        role_label: user.role === 'admin' ? 'Admin' : 'Viewer',
        entities_label: (user.allowed_entities ?? [])
          .map((id) => entityNameById.get(id) ?? id)
          .join(', '),
        default_label: user.default_entity_id
          ? entityNameById.get(user.default_entity_id) ?? user.default_entity_id
          : '—',
        pages_label: (user.allowed_pages ?? [])
          .map((id) => pageLabelById.get(id) ?? id)
          .join(', '),
        is_admin: user.role === 'admin' || adminIds.has(user.user_id),
        _user: user,
      })),
    [allUsers, adminIds, entityNameById, pageLabelById],
  );

  const columns: DataTableColumn[] = useMemo(
    () => [
      { key: 'name', label: 'Nom' },
      { key: 'email', label: 'Email' },
      { key: 'role_label', label: 'Rôle' },
      { key: 'entities_label', label: 'Périmètres' },
      { key: 'default_label', label: 'Défaut' },
      { key: 'pages_label', label: 'Pages' },
      {
        key: 'actions',
        label: 'Actions',
        renderHeader: () => <span className="normal-case tracking-normal">Actions</span>,
        renderCell: (record) => {
          if (record.is_admin) {
            return (
              <span className="text-xs text-[var(--text-muted)]">Lecture seule</span>
            );
          }
          const user = record._user as UserConfig;
          return (
            <div className="flex items-center gap-1 justify-center">
              <Button
                variant="ghost"
                className="!w-auto !min-h-8 !min-w-8 !px-2 !py-1"
                onPress={() => openEdit(user)}
                aria-label="Modifier"
              >
                <PencilIcon />
              </Button>
              <Button
                variant="ghost"
                className="!w-auto !min-h-8 !min-w-8 !px-2 !py-1 text-red-600"
                onPress={() => askDelete(user)}
                aria-label="Supprimer"
              >
                <TrashIcon />
              </Button>
            </div>
          );
        },
      },
    ],
    [],
  );

  function openCreate() {
    setForm({
      ...EMPTY_FORM,
      allowed_pages: pages[0] ? [pages[0].page_id] : [],
    });
    setError('');
    setModal({ mode: 'create' });
  }

  function openEdit(user: UserConfig) {
    setForm({
      name: user.name,
      email: user.email,
      allowed_entities: [...(user.allowed_entities ?? [])],
      allowed_pages: [...(user.allowed_pages ?? [])],
      default_entity_id: user.default_entity_id ?? null,
    });
    setError('');
    setModal({ mode: 'edit', user });
  }

  function closeModal() {
    if (pending) return;
    setModal(null);
  }

  function toggleEntity(entityId: EntityId) {
    setForm((current) => {
      const has = current.allowed_entities.includes(entityId);
      const allowed_entities = has
        ? current.allowed_entities.filter((id) => id !== entityId)
        : [...current.allowed_entities, entityId];
      // A default that is no longer allowed must be cleared.
      const default_entity_id =
        current.default_entity_id && allowed_entities.includes(current.default_entity_id)
          ? current.default_entity_id
          : null;
      return { ...current, allowed_entities, default_entity_id };
    });
  }

  function togglePage(pageId: PageId) {
    setForm((current) => {
      const has = current.allowed_pages.includes(pageId);
      return {
        ...current,
        allowed_pages: has
          ? current.allowed_pages.filter((id) => id !== pageId)
          : [...current.allowed_pages, pageId],
      };
    });
  }

  function selectAllPages() {
    setForm((current) => ({
      ...current,
      allowed_pages: pages.map((page) => page.page_id),
    }));
  }

  function deselectAllPages() {
    setForm((current) => ({
      ...current,
      allowed_pages: [],
    }));
  }

  function selectAllEntities() {
    setForm((current) => ({
      ...current,
      allowed_entities: entities.map((entity) => entity.entity_id),
      default_entity_id:
        current.default_entity_id &&
        entities.some((entity) => entity.entity_id === current.default_entity_id)
          ? current.default_entity_id
          : (entities[0]?.entity_id ?? null),
    }));
  }

  function deselectAllEntities() {
    setForm((current) => ({
      ...current,
      allowed_entities: [],
      default_entity_id: null,
    }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!modal || pending) return;
    setError('');
    setPending(true);

    try {
      const url =
        modal.mode === 'create'
          ? '/api/admin/users'
          : `/api/admin/users/${modal.user.user_id}`;
      const method = modal.mode === 'create' ? 'POST' : 'PUT';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = (await res.json().catch(() => null)) as
        | { user?: UserConfig; error?: string }
        | null;

      if (!res.ok || !data?.user) {
        setError(data?.error ?? "L'enregistrement a échoué.");
        return;
      }

      if (modal.mode === 'create') {
        setUsers((prev) => [...prev, data.user as UserConfig]);
      } else {
        setUsers((prev) =>
          prev.map((u) =>
            u.user_id === data.user!.user_id ? (data.user as UserConfig) : u,
          ),
        );
      }
      setModal(null);
      router.refresh();
    } catch {
      setError('Erreur de connexion.');
    } finally {
      setPending(false);
    }
  }

  function askDelete(user: UserConfig) {
    setDeleteError('');
    setConfirmUser(user);
  }

  function closeConfirm() {
    if (deletingId) return;
    setConfirmUser(null);
    setDeleteError('');
  }

  async function confirmDelete() {
    if (!confirmUser || deletingId) return;
    const user = confirmUser;
    setDeleteError('');
    setDeletingId(user.user_id);
    try {
      const res = await fetch(`/api/admin/users/${user.user_id}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => null)) as { error?: string } | null;
        setDeleteError(data?.error ?? 'La suppression a échoué.');
        return;
      }
      setUsers((prev) => prev.filter((u) => u.user_id !== user.user_id));
      setConfirmUser(null);
      router.refresh();
    } catch {
      setDeleteError('Erreur de connexion.');
    } finally {
      setDeletingId(null);
    }
  }

  const adminCount = adminUsers.length;
  const viewerCount = users.length;

  return (
    <div className="min-w-0 space-y-4">
      <div className="space-y-2">
        <p className="m-0 text-sm text-[var(--text-muted)]">
          {formatCount(adminCount, 'admin', 'admins')}
          {' · '}
          {formatCount(viewerCount, 'viewer', 'viewers')}
        </p>
        <div className="flex items-center justify-between gap-3">
          <ViewToggle value={view} onChange={setView} />
          <Button variant="primary" className="!w-auto !min-h-10" onPress={openCreate}>
            Ajouter un utilisateur
          </Button>
        </div>
      </div>

      {view === 'gallery' ? (
        allUsers.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">Aucun utilisateur.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4">
            {allUsers.map((user) => {
              const isAdmin = user.role === 'admin' || adminIds.has(user.user_id);
              const roleLabel = isAdmin ? 'Admin' : 'Viewer';
              const entitiesLabel = (user.allowed_entities ?? [])
                .map((id) => entityNameById.get(id) ?? id)
                .join(', ');
              return (
                <div
                  key={user.user_id}
                  className={`${galleryCard} flex flex-col gap-3 !cursor-default hover:!bg-[var(--surface)]`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-[var(--text)]"
                      aria-hidden
                    >
                      {userInitials(user.name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="m-0 font-semibold text-sm text-[var(--text)] truncate">
                        {user.name}
                      </p>
                      <p className="m-0 text-xs text-[var(--text-muted)] truncate">
                        {user.email}
                      </p>
                    </div>
                  </div>
                  <p className="m-0 text-xs text-[var(--text-muted)]">{roleLabel}</p>
                  {!isAdmin && entitiesLabel ? (
                    <p className="m-0 text-xs text-[var(--text-muted)] line-clamp-2">
                      {entitiesLabel}
                    </p>
                  ) : null}
                  {isAdmin ? (
                    <p className="m-0 text-xs text-[var(--text-muted)]">Lecture seule</p>
                  ) : (
                    <div className="mt-auto flex items-center gap-1">
                      <Button
                        variant="ghost"
                        className="!w-auto !min-h-8 !min-w-8 !px-2 !py-1"
                        onPress={() => openEdit(user)}
                        aria-label="Modifier"
                      >
                        <PencilIcon />
                      </Button>
                      <Button
                        variant="ghost"
                        className="!w-auto !min-h-8 !min-w-8 !px-2 !py-1 text-red-600"
                        onPress={() => askDelete(user)}
                        aria-label="Supprimer"
                      >
                        <TrashIcon />
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
      ) : (
        <DataTable
          records={records}
          columns={columns}
          emptyMessage="Aucun utilisateur."
          exportable={false}
          defaultPageSize={20}
        />
      )}

      {modal ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="user-modal-title"
        >
          <div className="w-full max-w-lg rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl">
            <h2 id="user-modal-title" className="type-title-3 m-0 mb-4">
              {modal.mode === 'create' ? 'Nouvel utilisateur' : 'Modifier l’utilisateur'}
            </h2>
            <form onSubmit={onSubmit} className="space-y-4">
              <TextField
                label="Nom"
                value={form.name}
                onChange={(name) => setForm((f) => ({ ...f, name }))}
                isRequired
                autoComplete="name"
              />
              <TextField
                label="Email"
                value={form.email}
                onChange={(email) => setForm((f) => ({ ...f, email }))}
                isRequired
                autoComplete="email"
              />

              <fieldset className="space-y-2">
                <legend className="w-full">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-[var(--text-muted)]">
                      Périmètres
                    </span>
                    <span className="flex gap-2 text-xs font-normal">
                      <button
                        type="button"
                        onClick={selectAllEntities}
                        className="text-[var(--secondary)] hover:underline"
                      >
                        Tout sélectionner
                      </button>
                      <span className="text-[var(--text-muted)]" aria-hidden>
                        ·
                      </span>
                      <button
                        type="button"
                        onClick={deselectAllEntities}
                        className="text-[var(--secondary)] hover:underline"
                      >
                        Tout désélectionner
                      </button>
                    </span>
                  </span>
                </legend>
                <div className="max-h-40 overflow-y-auto rounded-md border border-[var(--border)] p-3 space-y-2">
                  {entities.map((entity) => (
                    <label
                      key={entity.entity_id}
                      className="flex items-center gap-2 text-sm text-[var(--text)]"
                    >
                      <input
                        type="checkbox"
                        checked={form.allowed_entities.includes(entity.entity_id)}
                        onChange={() => toggleEntity(entity.entity_id)}
                        className="rounded border-[var(--border)]"
                      />
                      {entity.display_name}
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="space-y-1.5">
                <label
                  htmlFor="user-default-entity"
                  className="text-sm font-medium text-[var(--text-muted)]"
                >
                  Périmètre par défaut
                </label>
                <select
                  id="user-default-entity"
                  value={form.default_entity_id ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      default_entity_id: e.target.value ? (e.target.value as EntityId) : null,
                    }))
                  }
                  disabled={form.allowed_entities.length === 0}
                  className="w-full min-h-10 rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm text-[var(--text)] outline-none transition focus:border-[var(--secondary)] disabled:opacity-60"
                >
                  <option value="">Aucun (page d’accueil)</option>
                  {entities
                    .filter((entity) => form.allowed_entities.includes(entity.entity_id))
                    .map((entity) => (
                      <option key={entity.entity_id} value={entity.entity_id}>
                        {entity.display_name}
                      </option>
                    ))}
                </select>
                <p className="m-0 text-xs text-[var(--text-muted)]">
                  Périmètre affiché à la connexion. Doit faire partie des périmètres autorisés.
                </p>
              </div>

              <fieldset className="space-y-2">
                <legend className="w-full">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-[var(--text-muted)]">
                      Pages
                    </span>
                    <span className="flex gap-2 text-xs font-normal">
                      <button
                        type="button"
                        onClick={selectAllPages}
                        className="text-[var(--secondary)] hover:underline"
                      >
                        Tout sélectionner
                      </button>
                      <span className="text-[var(--text-muted)]" aria-hidden>
                        ·
                      </span>
                      <button
                        type="button"
                        onClick={deselectAllPages}
                        className="text-[var(--secondary)] hover:underline"
                      >
                        Tout désélectionner
                      </button>
                    </span>
                  </span>
                </legend>
                <div className="rounded-md border border-[var(--border)] p-3 space-y-2">
                  {pages.map((page) => (
                    <label
                      key={page.page_id}
                      className="flex items-center gap-2 text-sm text-[var(--text)]"
                    >
                      <input
                        type="checkbox"
                        checked={form.allowed_pages.includes(page.page_id)}
                        onChange={() => togglePage(page.page_id)}
                        className="rounded border-[var(--border)]"
                      />
                      {page.label}
                    </label>
                  ))}
                </div>
              </fieldset>

              {error ? <p className="text-sm text-red-600 m-0">{error}</p> : null}

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="ghost"
                  className="!w-auto"
                  onPress={closeModal}
                  isDisabled={pending}
                >
                  Annuler
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  className="!w-auto"
                  isDisabled={pending}
                >
                  {pending ? 'Enregistrement…' : 'Enregistrer'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {confirmUser ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-modal-title"
        >
          <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl">
            <h2 id="delete-modal-title" className="type-title-3 m-0 mb-2">
              Supprimer l’utilisateur ?
            </h2>
            <p className="text-sm text-[var(--text-muted)] mb-4">
              {confirmUser.name} ({confirmUser.email}) sera retiré de l’application.
              Cette action est irréversible.
            </p>
            {deleteError ? (
              <p className="text-sm text-red-600 mb-3">{deleteError}</p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                className="!w-auto"
                onPress={closeConfirm}
                isDisabled={Boolean(deletingId)}
              >
                Annuler
              </Button>
              <Button
                variant="primary"
                className="!w-auto !bg-red-600"
                onPress={confirmDelete}
                isDisabled={Boolean(deletingId)}
              >
                {deletingId ? 'Suppression…' : 'Supprimer'}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PencilIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

function formatCount(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
