'use client';

import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import {
  ExternalLink,
  FolderKanban,
  Pencil,
  Plus,
  Search,
  Settings,
  Trash2,
  Users,
  X,
} from 'lucide-react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useWorkspaceStore } from '@/stores/workspace';

interface OrgWorkspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  organization_id: string | null;
  created_at: string;
  updated_at: string;
  logo_url?: string | null;
  logo_emoji?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
  background_color?: string | null;
  sidebar_color?: string | null;
  font_family?: string | null;
  platform_drive_enabled?: boolean;
  system_drive_enabled?: boolean;
  organization_logo_url?: string | null;
  organization_logo_rectangle_url?: string | null;
}

const slugify = (value: string): string => {
  const base = value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  // Backend requires min 2 chars matching ^[a-z0-9][a-z0-9-]*[a-z0-9]$
  if (base.length === 1) return `${base}-ws`;
  return base;
};

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;

const formatErrorDetail = (detail: unknown): string => {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: string[]; msg?: string }) =>
        d.msg ? `${(d.loc || []).slice(-1).join('') || 'field'}: ${d.msg}` : JSON.stringify(d)
      )
      .join('; ');
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
};

const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return '—';
  }
};

const deleteKey = (name: string) => name.toLowerCase().replace(/\s+/g, '');

type FormState = {
  name: string;
  slug: string;
  logo_emoji: string;
  logo_url: string;
  primary_color: string;
};

const EMPTY_FORM: FormState = {
  name: '',
  slug: '',
  logo_emoji: '📁',
  logo_url: '',
  primary_color: '#22c55e',
};

export default function OrganizationWorkspacesPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const refreshWorkspaceStore = useWorkspaceStore((s) => s.fetchWorkspaces);

  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [createForm, setCreateForm] = useState<FormState>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<FormState>(EMPTY_FORM);
  const [savingId, setSavingId] = useState<string | null>(null);

  // Delete confirmation modal
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('');
  const [deleting, setDeleting] = useState(false);
  const deleteInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (deleteTarget) {
      setTimeout(() => deleteInputRef.current?.focus(), 50);
    }
  }, [deleteTarget]);

  const fetchWorkspaces = useCallback(async () => {
    if (!orgId) return;
    try {
      const response = await authFetch(`/api/organizations/${orgId}/workspaces`);
      if (response.ok) {
        const data: OrgWorkspace[] = await response.json();
        setWorkspaces(data);
        setError(null);
      } else {
        setError(`Failed to load workspaces (${response.status})`);
      }
    } catch (err) {
      console.error('Failed to fetch org workspaces:', err);
      setError('Failed to load workspaces');
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void fetchWorkspaces();
  }, [fetchWorkspaces]);

  const filtered = searchQuery.trim()
    ? workspaces.filter(
        (w) =>
          w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          w.slug.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : workspaces;

  const resetCreate = () => {
    setShowAddForm(false);
    setCreateForm(EMPTY_FORM);
    setCreateError(null);
  };

  const handleCreate = async () => {
    const name = createForm.name.trim();
    const slug = createForm.slug.trim();
    if (!name || !slug) return;
    if (!SLUG_PATTERN.test(slug)) {
      setCreateError(
        'Slug must be at least 2 characters, lowercase letters/digits/dashes, and start and end with a letter or digit.'
      );
      return;
    }
    setCreateError(null);
    setCreating(true);
    try {
      const response = await authFetch(`/api/organizations/${orgId}/workspaces`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          slug,
          logo_emoji: createForm.logo_emoji || null,
          logo_url: createForm.logo_url || null,
          primary_color: createForm.primary_color || '#22c55e',
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setCreateError(
          formatErrorDetail(body?.detail) || `Failed to create workspace (${response.status})`
        );
        return;
      }
      const created: OrgWorkspace = await response.json();
      setWorkspaces((prev) =>
        [...prev, created].sort((a, b) => a.name.localeCompare(b.name))
      );
      void refreshWorkspaceStore();
      resetCreate();
    } catch (err) {
      console.error('Failed to create workspace:', err);
      setCreateError('Network error while creating workspace.');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (ws: OrgWorkspace) => {
    setEditingId(ws.id);
    setEditError(null);
    setEditForm({
      name: ws.name,
      slug: ws.slug,
      logo_emoji: ws.logo_emoji || '',
      logo_url: ws.logo_url || '',
      primary_color: ws.primary_color || '#22c55e',
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(EMPTY_FORM);
    setEditError(null);
  };

  const handleUpdate = async (workspaceId: string) => {
    setSavingId(workspaceId);
    setEditError(null);
    try {
      const response = await authFetch(`/api/organizations/${orgId}/workspaces/${workspaceId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editForm.name.trim() || null,
          logo_emoji: editForm.logo_emoji || null,
          logo_url: editForm.logo_url || null,
          primary_color: editForm.primary_color || null,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setEditError(
          formatErrorDetail(body?.detail) || `Failed to update workspace (${response.status})`
        );
        return;
      }
      const updated: OrgWorkspace = await response.json();
      setWorkspaces((prev) => prev.map((w) => (w.id === workspaceId ? updated : w)));
      void refreshWorkspaceStore();
      cancelEdit();
    } catch (err) {
      console.error('Failed to update workspace:', err);
      setEditError('Network error while updating workspace.');
    } finally {
      setSavingId(null);
    }
  };

  const openDeleteModal = (ws: OrgWorkspace) => {
    setDeleteTarget({ id: ws.id, name: ws.name });
    setDeleteConfirmInput('');
  };

  const closeDeleteModal = () => {
    setDeleteTarget(null);
    setDeleteConfirmInput('');
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const response = await authFetch(
        `/api/organizations/${orgId}/workspaces/${deleteTarget.id}`,
        { method: 'DELETE' }
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(
          formatErrorDetail(body?.detail) ||
            `Failed to delete workspace (${response.status})`
        );
        closeDeleteModal();
        return;
      }
      setWorkspaces((prev) => prev.filter((w) => w.id !== deleteTarget.id));
      void refreshWorkspaceStore();
      if (editingId === deleteTarget.id) cancelEdit();
      closeDeleteModal();
    } catch (err) {
      console.error('Failed to delete workspace:', err);
      setError('Failed to delete workspace');
      closeDeleteModal();
    } finally {
      setDeleting(false);
    }
  };

  const renderLogo = (ws: OrgWorkspace) => {
    const API_BASE = getApiUrl();
    const normalize = (url?: string | null) =>
      url && url.startsWith('/') ? `${API_BASE}${url}` : url || undefined;
    const logo =
      normalize(ws.logo_url) ||
      normalize(ws.organization_logo_url) ||
      normalize(ws.organization_logo_rectangle_url);
    const bg = ws.primary_color ? `${ws.primary_color}20` : '#22c55e20';
    return (
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg overflow-hidden text-lg"
        style={{ backgroundColor: bg }}
      >
        {logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logo} alt={ws.name} className="h-full w-full object-contain p-0.5" />
        ) : (
          <span>{ws.logo_emoji || '📁'}</span>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading workspaces...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Delete confirmation modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-md rounded-xl border bg-background p-6 shadow-xl">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-base font-semibold">Delete workspace</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  This action is permanent and cannot be undone.
                </p>
              </div>
              <button
                onClick={closeDeleteModal}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>
            <p className="mb-3 text-sm text-muted-foreground">
              To confirm, type{' '}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
                {deleteKey(deleteTarget.name)}
              </code>{' '}
              below:
            </p>
            <input
              ref={deleteInputRef}
              type="text"
              value={deleteConfirmInput}
              onChange={(e) => setDeleteConfirmInput(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === 'Enter' &&
                  deleteConfirmInput === deleteKey(deleteTarget.name) &&
                  !deleting
                ) {
                  void handleDelete();
                }
                if (e.key === 'Escape') closeDeleteModal();
              }}
              placeholder={deleteKey(deleteTarget.name)}
              className="mb-4 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-red-500/30"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDelete()}
                disabled={deleteConfirmInput !== deleteKey(deleteTarget.name) || deleting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40"
              >
                {deleting ? 'Deleting...' : 'Delete workspace'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Workspaces</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {filtered.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage workspaces belonging to this organization
          </p>
        </div>
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus size={16} />
          Add Workspace
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-500">
          {error}
        </div>
      )}

      {showAddForm && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <h3 className="mb-4 font-medium">Create New Workspace</h3>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Name *</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm((f) => ({
                      ...f,
                      name: e.target.value,
                      slug: f.slug || slugify(e.target.value),
                    }))
                  }
                  placeholder="Workspace name"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Slug *</label>
                <input
                  type="text"
                  value={createForm.slug}
                  onChange={(e) => setCreateForm((f) => ({ ...f, slug: slugify(e.target.value) }))}
                  placeholder="workspace-slug"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Emoji</label>
                <input
                  type="text"
                  value={createForm.logo_emoji}
                  onChange={(e) => setCreateForm((f) => ({ ...f, logo_emoji: e.target.value }))}
                  placeholder="📁"
                  maxLength={4}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div className="col-span-2">
                <label className="mb-1 block text-sm font-medium">Logo URL (optional)</label>
                <input
                  type="text"
                  value={createForm.logo_url}
                  onChange={(e) => setCreateForm((f) => ({ ...f, logo_url: e.target.value }))}
                  placeholder="https://..."
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Primary Color</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={createForm.primary_color}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, primary_color: e.target.value }))
                  }
                  className="h-9 w-12 cursor-pointer rounded border bg-background"
                />
                <input
                  type="text"
                  value={createForm.primary_color}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, primary_color: e.target.value }))
                  }
                  className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
            {createError && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-500">
                {createError}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={resetCreate}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
                disabled={creating}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !createForm.name.trim() || !createForm.slug.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {creating ? 'Creating...' : 'Create Workspace'}
              </button>
            </div>
          </div>
        </div>
      )}

      {workspaces.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <FolderKanban size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No workspaces yet</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Create your first workspace to get started
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Workspace
          </button>
        </div>
      ) : (
        <div>
          <div className="mb-4 relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              placeholder="Search workspaces..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border bg-background pl-10 pr-10 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm">
                  <th className="p-3 font-medium">Workspace</th>
                  <th className="p-3 font-medium">Slug</th>
                  <th className="p-3 font-medium">Created</th>
                  <th className="p-3 font-medium w-48">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-muted-foreground">
                      {searchQuery ? `No workspaces match "${searchQuery}"` : 'No workspaces'}
                    </td>
                  </tr>
                ) : (
                  filtered.map((ws) => (
                    <Fragment key={ws.id}>
                      <tr
                        className={cn(
                          'border-b transition-colors',
                          editingId === ws.id ? 'bg-muted/20' : 'hover:bg-muted/30'
                        )}
                      >
                        <td className="p-3 align-top">
                          <Link
                            href={`/organizations/${orgId}/settings/workspaces/${ws.id}`}
                            className="flex items-center gap-3 min-h-[2.5rem] group"
                          >
                            {renderLogo(ws)}
                            <div className="min-w-0 flex-1">
                              <p className="font-medium group-hover:underline">{ws.name}</p>
                              <p className="text-xs text-muted-foreground truncate">{ws.id}</p>
                            </div>
                          </Link>
                        </td>
                        <td className="p-3 align-middle">
                          <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                            /{ws.slug}
                          </code>
                        </td>
                        <td className="p-3 align-middle text-sm text-muted-foreground">
                          {formatDate(ws.created_at)}
                        </td>
                        <td className="p-3 align-middle">
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() =>
                                editingId === ws.id ? cancelEdit() : startEdit(ws)
                              }
                              className={cn(
                                'rounded p-1.5 hover:bg-muted',
                                editingId === ws.id
                                  ? 'bg-primary/10 text-primary'
                                  : 'text-muted-foreground'
                              )}
                              title={editingId === ws.id ? 'Cancel edit' : 'Edit'}
                            >
                              <Pencil size={14} />
                            </button>
                            <Link
                              href={`/workspace/${ws.id}/settings`}
                              className="rounded p-1.5 text-muted-foreground hover:bg-muted"
                              title="Open workspace settings"
                            >
                              <Settings size={14} />
                            </Link>
                            <Link
                              href={`/workspace/${ws.id}/chat`}
                              className="rounded p-1.5 text-muted-foreground hover:bg-muted"
                              title="Open workspace"
                            >
                              <ExternalLink size={14} />
                            </Link>
                            <button
                              onClick={() => openDeleteModal(ws)}
                              className="rounded p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                      {editingId === ws.id && (
                        <tr className="border-b bg-muted/10">
                          <td colSpan={4} className="p-4">
                            <div className="grid gap-3">
                              <div className="grid grid-cols-2 gap-3">
                                <div>
                                  <label className="mb-1 block text-xs font-medium">Name</label>
                                  <input
                                    type="text"
                                    value={editForm.name}
                                    onChange={(e) =>
                                      setEditForm((f) => ({ ...f, name: e.target.value }))
                                    }
                                    className="w-full rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                                  />
                                </div>
                                <div>
                                  <label className="mb-1 block text-xs font-medium">
                                    Slug (read-only)
                                  </label>
                                  <input
                                    type="text"
                                    value={editForm.slug}
                                    disabled
                                    className="w-full rounded-lg border bg-muted px-3 py-1.5 text-sm text-muted-foreground"
                                  />
                                </div>
                              </div>
                              <div className="grid grid-cols-3 gap-3">
                                <div>
                                  <label className="mb-1 block text-xs font-medium">Emoji</label>
                                  <input
                                    type="text"
                                    value={editForm.logo_emoji}
                                    onChange={(e) =>
                                      setEditForm((f) => ({ ...f, logo_emoji: e.target.value }))
                                    }
                                    maxLength={4}
                                    className="w-full rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                                  />
                                </div>
                                <div className="col-span-2">
                                  <label className="mb-1 block text-xs font-medium">Logo URL</label>
                                  <input
                                    type="text"
                                    value={editForm.logo_url}
                                    onChange={(e) =>
                                      setEditForm((f) => ({ ...f, logo_url: e.target.value }))
                                    }
                                    placeholder="https://..."
                                    className="w-full rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                                  />
                                </div>
                              </div>
                              <div>
                                <label className="mb-1 block text-xs font-medium">
                                  Primary Color
                                </label>
                                <div className="flex items-center gap-2">
                                  <input
                                    type="color"
                                    value={editForm.primary_color}
                                    onChange={(e) =>
                                      setEditForm((f) => ({
                                        ...f,
                                        primary_color: e.target.value,
                                      }))
                                    }
                                    className="h-8 w-12 cursor-pointer rounded border bg-background"
                                  />
                                  <input
                                    type="text"
                                    value={editForm.primary_color}
                                    onChange={(e) =>
                                      setEditForm((f) => ({
                                        ...f,
                                        primary_color: e.target.value,
                                      }))
                                    }
                                    className="flex-1 rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                                  />
                                </div>
                              </div>
                              {editError && (
                                <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-500">
                                  {editError}
                                </div>
                              )}
                              <div className="flex justify-end gap-2">
                                <button
                                  onClick={cancelEdit}
                                  className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
                                  disabled={savingId === ws.id}
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={() => handleUpdate(ws.id)}
                                  disabled={savingId === ws.id || !editForm.name.trim()}
                                  className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                                >
                                  {savingId === ws.id ? 'Saving...' : 'Save'}
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-sm text-muted-foreground">
          Workspaces inherit branding from the organization but can customize their own themes. Use{' '}
          <Users size={12} className="inline" /> the workspace settings link for full configuration
          including members, drives, and integrations.
        </p>
      </div>
    </div>
  );
}
