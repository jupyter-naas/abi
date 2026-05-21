'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowLeft, FolderKanban, Trash2, X } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
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

const deleteKey = (name: string) => name.toLowerCase().replace(/\s+/g, '');

type FormState = {
  name: string;
  logo_emoji: string;
  logo_url: string;
  primary_color: string;
};

export default function WorkspaceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const orgId = params.orgId as string;
  const workspaceId = params.workspaceId as string;
  const refreshWorkspaceStore = useWorkspaceStore((s) => s.fetchWorkspaces);

  const [workspace, setWorkspace] = useState<OrgWorkspace | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    name: '',
    logo_emoji: '',
    logo_url: '',
    primary_color: '#22c55e',
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Delete modal
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('');
  const [deleting, setDeleting] = useState(false);
  const deleteInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showDelete) {
      setDeleteConfirmInput('');
      setTimeout(() => deleteInputRef.current?.focus(), 50);
    }
  }, [showDelete]);

  const fetchWorkspace = useCallback(async () => {
    if (!orgId || !workspaceId) return;
    setLoading(true);
    try {
      const response = await authFetch(
        `/api/organizations/${orgId}/workspaces/${workspaceId}`
      );
      if (response.status === 404) {
        setNotFound(true);
        return;
      }
      if (!response.ok) {
        setFetchError(`Failed to load workspace (${response.status})`);
        return;
      }
      const data: OrgWorkspace = await response.json();
      setWorkspace(data);
      setForm({
        name: data.name,
        logo_emoji: data.logo_emoji || '',
        logo_url: data.logo_url || '',
        primary_color: data.primary_color || '#22c55e',
      });
    } catch (err) {
      console.error('Failed to fetch workspace:', err);
      setFetchError('Failed to load workspace');
    } finally {
      setLoading(false);
    }
  }, [orgId, workspaceId]);

  useEffect(() => {
    void fetchWorkspace();
  }, [fetchWorkspace]);

  const handleSave = async () => {
    if (!workspace) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const response = await authFetch(
        `/api/organizations/${orgId}/workspaces/${workspaceId}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: form.name.trim() || null,
            logo_emoji: form.logo_emoji || null,
            logo_url: form.logo_url || null,
            primary_color: form.primary_color || null,
          }),
        }
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setSaveError(
          formatErrorDetail(body?.detail) || `Failed to update workspace (${response.status})`
        );
        return;
      }
      const updated: OrgWorkspace = await response.json();
      setWorkspace(updated);
      setForm({
        name: updated.name,
        logo_emoji: updated.logo_emoji || '',
        logo_url: updated.logo_url || '',
        primary_color: updated.primary_color || '#22c55e',
      });
      void refreshWorkspaceStore();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to update workspace:', err);
      setSaveError('Network error while updating workspace.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const response = await authFetch(
        `/api/organizations/${orgId}/workspaces/${workspaceId}`,
        { method: 'DELETE' }
      );
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setSaveError(
          formatErrorDetail(body?.detail) || `Failed to delete workspace (${response.status})`
        );
        setShowDelete(false);
        return;
      }
      void refreshWorkspaceStore();
      router.push(`/organizations/${orgId}/settings/workspaces`);
    } catch (err) {
      console.error('Failed to delete workspace:', err);
      setSaveError('Failed to delete workspace.');
      setShowDelete(false);
    } finally {
      setDeleting(false);
    }
  };

  const renderLogo = () => {
    if (!workspace) return null;
    const API_BASE = getApiUrl();
    const normalize = (url?: string | null) =>
      url && url.startsWith('/') ? `${API_BASE}${url}` : url || undefined;
    const logo =
      normalize(form.logo_url) ||
      normalize(workspace.organization_logo_url) ||
      normalize(workspace.organization_logo_rectangle_url);
    const bg = form.primary_color ? `${form.primary_color}20` : '#22c55e20';
    return (
      <div
        className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl overflow-hidden text-3xl"
        style={{ backgroundColor: bg }}
      >
        {logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logo} alt={workspace.name} className="h-full w-full object-contain p-1" />
        ) : (
          <span>{form.logo_emoji || '📁'}</span>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-muted-foreground">Loading workspace...</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="space-y-6">
        <Link
          href={`/organizations/${orgId}/settings/workspaces`}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={16} />
          Back to workspaces
        </Link>
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <FolderKanban size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">Workspace not found</h3>
          <p className="text-sm text-muted-foreground">
            This workspace may have been deleted or you don&apos;t have access.
          </p>
        </div>
      </div>
    );
  }

  if (fetchError || !workspace) {
    return (
      <div className="space-y-4">
        <Link
          href={`/organizations/${orgId}/settings/workspaces`}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={16} />
          Back to workspaces
        </Link>
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-500">
          {fetchError ?? 'Unknown error'}
        </div>
      </div>
    );
  }

  const confirmKey = deleteKey(workspace.name);
  const isDirty =
    form.name !== workspace.name ||
    form.logo_emoji !== (workspace.logo_emoji || '') ||
    form.logo_url !== (workspace.logo_url || '') ||
    form.primary_color !== (workspace.primary_color || '#22c55e');

  return (
    <div className="space-y-6">
      {/* Delete confirmation modal */}
      {showDelete && (
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
                onClick={() => setShowDelete(false)}
                className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>
            <p className="mb-3 text-sm text-muted-foreground">
              To confirm, type{' '}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">
                {confirmKey}
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
                  deleteConfirmInput === confirmKey &&
                  !deleting
                ) {
                  void handleDelete();
                }
                if (e.key === 'Escape') setShowDelete(false);
              }}
              placeholder={confirmKey}
              className="mb-4 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-red-500/30"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDelete(false)}
                disabled={deleting}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDelete()}
                disabled={deleteConfirmInput !== confirmKey || deleting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-40"
              >
                {deleting ? 'Deleting...' : 'Delete workspace'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div>
        <Link
          href={`/organizations/${orgId}/settings/workspaces`}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft size={16} />
          Back to workspaces
        </Link>
        <div className="flex items-center gap-4">
          {renderLogo()}
          <div>
            <h2 className="text-xl font-semibold">{workspace.name}</h2>
            <code className="text-xs text-muted-foreground">/{workspace.slug}</code>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="rounded-lg border bg-muted/10 p-6 space-y-5">
        <h3 className="font-medium">Workspace settings</h3>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Workspace name"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Slug (read-only)</label>
            <input
              type="text"
              value={workspace.slug}
              disabled
              className="w-full rounded-lg border bg-muted px-3 py-2 text-sm text-muted-foreground"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Emoji</label>
            <input
              type="text"
              value={form.logo_emoji}
              onChange={(e) => setForm((f) => ({ ...f, logo_emoji: e.target.value }))}
              placeholder="📁"
              maxLength={4}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="col-span-2">
            <label className="mb-1 block text-sm font-medium">Logo URL (optional)</label>
            <input
              type="text"
              value={form.logo_url}
              onChange={(e) => setForm((f) => ({ ...f, logo_url: e.target.value }))}
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
              value={form.primary_color}
              onChange={(e) => setForm((f) => ({ ...f, primary_color: e.target.value }))}
              className="h-9 w-12 cursor-pointer rounded border bg-background"
            />
            <input
              type="text"
              value={form.primary_color}
              onChange={(e) => setForm((f) => ({ ...f, primary_color: e.target.value }))}
              className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        {saveError && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-500">
            {saveError}
          </div>
        )}
        {saveSuccess && (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-600">
            Workspace updated successfully.
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={() => {
              if (workspace) {
                setForm({
                  name: workspace.name,
                  logo_emoji: workspace.logo_emoji || '',
                  logo_url: workspace.logo_url || '',
                  primary_color: workspace.primary_color || '#22c55e',
                });
                setSaveError(null);
                setSaveSuccess(false);
              }
            }}
            disabled={!isDirty || saving}
            className="rounded-lg border px-4 py-2 text-sm hover:bg-muted disabled:opacity-40"
          >
            Discard
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={saving || !form.name.trim() || !isDirty}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </div>
      </div>

      {/* Danger zone */}
      <div className="rounded-lg border border-red-500/30 p-6 space-y-3">
        <h3 className="font-medium text-red-600">Danger zone</h3>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium">Delete this workspace</p>
            <p className="text-xs text-muted-foreground">
              Permanently remove this workspace and all its data. This cannot be undone.
            </p>
          </div>
          <button
            onClick={() => setShowDelete(true)}
            className="flex shrink-0 items-center gap-2 rounded-lg border border-red-500/40 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
          >
            <Trash2 size={14} />
            Delete workspace
          </button>
        </div>
      </div>
    </div>
  );
}
