'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { AlertCircle, Check, ChevronDown, Loader2, Network, Plus, Save, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';

interface CreatedGraph {
  id: string;
  uri: string;
  label: string;
  role_label: string;
}

interface ApiGraphInfo {
  id: string;
  uri: string;
  label: string;
  role_label: string;
}

interface ApiGraphPack {
  role_label: string;
  graphs: ApiGraphInfo[];
}

function formatRoleLabel(role: string): string {
  if (!role || role === 'unknown') return 'Unknown';
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function normalizeRoleLabel(input: string): string {
  return input.trim().toLowerCase();
}

function RolePicker({
  value,
  options,
  disabled,
  onChange,
}: {
  value: string;
  options: string[];
  disabled?: boolean;
  onChange: (role: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number; width: number } | null>(
    null,
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setPopoverPos(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const reposition = () => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        setPopoverPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((role) => role.includes(q) || formatRoleLabel(role).toLowerCase().includes(q));
  }, [options, query]);

  const trimmed = query.trim();
  const normalizedQuery = normalizeRoleLabel(trimmed);
  const isAdminAttempt = normalizedQuery === 'admin';
  const canCreate =
    normalizedQuery.length > 0 &&
    !isAdminAttempt &&
    !options.some((role) => role === normalizedQuery);

  const handlePick = (role: string) => {
    setOpen(false);
    if (role !== value) onChange(role);
  };

  const handleCreate = () => {
    if (!canCreate) return;
    setOpen(false);
    onChange(normalizedQuery);
  };

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          setOpen((v) => !v);
        }}
        className={cn(
          'flex w-full items-center justify-between rounded-lg border bg-background px-4 py-2 text-sm outline-none',
          'focus:ring-2 focus:ring-primary',
          disabled && 'cursor-not-allowed opacity-50',
        )}
      >
        <span>{formatRoleLabel(value)}</span>
        <ChevronDown size={16} className={cn('text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>

      {open && popoverPos && typeof document !== 'undefined' && createPortal(
        <>
          <div
            className="fixed inset-0 z-[9998]"
            onClick={() => setOpen(false)}
          />
          <div
            style={{ top: popoverPos.top, left: popoverPos.left, width: popoverPos.width }}
            className="fixed z-[9999] rounded-md border border-border bg-popover p-1 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  if (canCreate) {
                    handleCreate();
                  } else if (filtered.length > 0) {
                    handlePick(filtered[0]);
                  }
                } else if (e.key === 'Escape') {
                  setOpen(false);
                }
              }}
              placeholder="Search or create role..."
              className="mb-1 w-full rounded border-0 bg-muted px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary/30"
            />
            <div className="max-h-60 overflow-y-auto">
              {filtered.map((role) => {
                const isSelected = role === value;
                return (
                  <button
                    key={role}
                    type="button"
                    onClick={() => handlePick(role)}
                    className="flex w-full items-center justify-between gap-2 rounded px-3 py-2 text-left text-sm hover:bg-accent"
                  >
                    <span>{formatRoleLabel(role)}</span>
                    {isSelected && <Check size={14} className="text-muted-foreground" />}
                  </button>
                );
              })}
              {filtered.length === 0 && !canCreate && (
                <p className="px-3 py-2 text-sm text-muted-foreground">
                  {isAdminAttempt ? 'Admin role cannot be assigned' : 'No matching role'}
                </p>
              )}
              {canCreate && (
                <button
                  type="button"
                  onClick={handleCreate}
                  className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm hover:bg-accent"
                >
                  <Plus size={14} className="text-muted-foreground" />
                  <span>
                    Create{' '}
                    <span className="font-medium text-foreground">
                      &ldquo;{formatRoleLabel(normalizedQuery)}&rdquo;
                    </span>
                  </span>
                </button>
              )}
            </div>
          </div>
        </>,
        document.body,
      )}
    </div>
  );
}

export default function CreateGraphPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const { selectGraph, setVisibleGraphs } = useKnowledgeGraphStore();

  // When `?edit=<graph uri>` is present we load that graph and switch to update mode.
  const editUri = searchParams.get('edit');
  const isEditing = Boolean(editUri);

  const [label, setLabel] = useState('');
  const [description, setDescription] = useState('');
  const [roleLabel, setRoleLabel] = useState('unknown');
  const [roles, setRoles] = useState<string[]>(['unknown']);
  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreatedGraph | null>(null);

  const selectableRoles = useMemo(
    () => roles.filter((role) => role.trim().toLowerCase() !== 'admin'),
    [roles],
  );

  const roleOptions = useMemo(() => {
    const merged = new Set(selectableRoles);
    if (roleLabel && roleLabel !== 'admin') merged.add(roleLabel);
    return Array.from(merged).sort((a, b) => formatRoleLabel(a).localeCompare(formatRoleLabel(b)));
  }, [selectableRoles, roleLabel]);

  const graphsForSelectedRole = useMemo(
    () => graphPacks.find((pack) => pack.role_label === roleLabel)?.graphs ?? [],
    [graphPacks, roleLabel],
  );

  const loadRoles = useCallback(async () => {
    setRolesLoading(true);
    try {
      const [rolesRes, listRes] = await Promise.all([
        authFetch(
          `${getApiUrl()}/api/graph/roles?workspace_id=${encodeURIComponent(workspaceId)}`,
        ),
        authFetch(
          `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`,
        ),
      ]);
      let knownRoles: string[] = ['unknown'];
      if (rolesRes.ok) {
        const roleData = (await rolesRes.json()) as string[];
        const normalized = Array.isArray(roleData)
          ? roleData.map((r) => r.trim().toLowerCase()).filter(Boolean)
          : [];
        knownRoles = normalized.includes('unknown') ? normalized : [...normalized, 'unknown'];
      }
      if (listRes.ok) {
        const packs = (await listRes.json()) as ApiGraphPack[];
        setGraphPacks(Array.isArray(packs) ? packs : []);
      }

      // In edit mode, load the target graph and pre-fill the form from its current values.
      if (editUri) {
        const detailRes = await authFetch(
          `${getApiUrl()}/api/graph/detail?workspace_id=${encodeURIComponent(workspaceId)}` +
            `&uri=${encodeURIComponent(editUri)}`,
        );
        if (detailRes.ok) {
          const detail = (await detailRes.json()) as {
            label: string;
            description: string | null;
            role_label: string;
          };
          setLabel(detail.label ?? '');
          setDescription(detail.description ?? '');
          const detailRole = (detail.role_label || 'unknown').trim().toLowerCase();
          if (detailRole && !knownRoles.includes(detailRole)) knownRoles = [...knownRoles, detailRole];
          setRoles(knownRoles);
          setRoleLabel(detailRole || 'unknown');
        } else {
          setRoles(knownRoles);
          const payload = await detailRes.json().catch(() => ({}));
          setError(
            typeof payload?.detail === 'string' ? payload.detail : 'Failed to load graph for editing',
          );
        }
      } else {
        setRoles(knownRoles);
        setRoleLabel((prev) => {
          const writable = knownRoles.filter((r) => r !== 'admin');
          if (writable.includes(prev)) return prev;
          return writable[0] ?? 'unknown';
        });
      }
    } catch {
      setRoles(['unknown']);
      setGraphPacks([]);
    } finally {
      setRolesLoading(false);
    }
  }, [workspaceId, editUri]);

  useEffect(() => {
    void loadRoles();
  }, [loadRoles]);

  const handleRoleChange = (nextRole: string) => {
    const normalized = normalizeRoleLabel(nextRole);
    if (!normalized || normalized === 'admin') return;
    setRoleLabel(normalized);
    setRoles((prev) => (prev.includes(normalized) ? prev : [...prev, normalized]));
  };

  const handleCancel = () => {
    router.push(`/workspace/${workspaceId}/graph/network`);
  };

  const handleSubmit = async () => {
    const trimmedLabel = label.trim();
    if (!trimmedLabel || !roleLabel) return;

    setCreating(true);
    setError(null);
    try {
      const endpoint = isEditing ? '/api/graph/update' : '/api/graph/create';
      const body = isEditing
        ? {
            workspace_id: workspaceId,
            uri: editUri,
            label: trimmedLabel,
            description: description.trim() || null,
            role_label: roleLabel,
          }
        : {
            workspace_id: workspaceId,
            label: trimmedLabel,
            description: description.trim() || null,
            role_label: roleLabel,
          };
      const res = await authFetch(`${getApiUrl()}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        const fallback = isEditing
          ? `Failed to update graph (${res.status})`
          : `Failed to create graph (${res.status})`;
        const message = typeof payload?.detail === 'string' ? payload.detail : fallback;
        throw new Error(message);
      }
      const data = (await res.json()) as CreatedGraph;
      setCreated(data);
      selectGraph(data.id);
      setVisibleGraphs([data.id]);
      window.dispatchEvent(new CustomEvent('graph-list-update'));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : isEditing
            ? 'Failed to update graph'
            : 'Failed to create graph',
      );
    } finally {
      setCreating(false);
    }
  };

  const openGraph = () => {
    if (!created) return;
    router.push(`/workspace/${workspaceId}/graph/explore`);
  };

  const resetForm = () => {
    setCreated(null);
    setLabel('');
    setDescription('');
    setRoleLabel(selectableRoles[0] ?? 'unknown');
  };

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 flex-col overflow-y-auto bg-card p-6">
        <div className="mx-auto w-full max-w-2xl">
          <div className="mb-6 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Network size={24} className="text-workspace-accent" />
              <div>
                <h2 className="text-lg font-semibold">{isEditing ? 'Edit Graph' : 'New Graph'}</h2>
                <p className="text-sm text-muted-foreground">
                  {isEditing
                    ? 'Update this graph’s label, role and description.'
                    : 'Create a new named graph in the triple store.'}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleCancel}
              className="rounded p-2 text-muted-foreground hover:bg-muted"
              title="Close"
            >
              <X size={20} />
            </button>
          </div>

          {created ? (
            <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
              <p className="text-sm font-medium text-foreground">
                Graph &quot;{created.label}&quot; {isEditing ? 'updated' : 'created'} successfully.
              </p>
              <p className="text-xs text-muted-foreground">
                Role: {formatRoleLabel(created.role_label)}
              </p>
              <p className="break-all text-xs text-muted-foreground">{created.uri}</p>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={isEditing ? handleCancel : resetForm}
                  className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  {isEditing ? 'Back to Network' : 'Create another'}
                </button>
                <button
                  type="button"
                  onClick={openGraph}
                  className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
                >
                  Open in Explore
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              <div>
                <label className="mb-2 block text-sm font-medium">Label *</label>
                <input
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="e.g., Customer Knowledge Graph"
                  className="w-full rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">Role *</label>
                {rolesLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                    <Loader2 size={14} className="animate-spin" />
                    Loading roles...
                  </div>
                ) : (
                  <RolePicker
                    value={roleLabel}
                    options={roleOptions}
                    onChange={handleRoleChange}
                  />
                )}
                <div className="mt-3 rounded-lg border bg-muted/20 px-4 py-3">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Existing graphs in this role
                  </p>
                  {rolesLoading ? (
                    <p className="text-xs text-muted-foreground">Loading...</p>
                  ) : graphsForSelectedRole.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No graphs currently use the &quot;{formatRoleLabel(roleLabel)}&quot; role.
                    </p>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      {graphsForSelectedRole.map((graph) => (
                        <li key={graph.uri} className="flex items-center justify-between gap-2">
                          <span className="truncate">{graph.label}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">{graph.id}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">
                  Description
                  <span className="ml-2 text-xs font-normal text-muted-foreground">(optional)</span>
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Short description of this graph..."
                  rows={3}
                  className="w-full resize-none rounded-lg border bg-background px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  {error}
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleCancel}
                  className="flex-1 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void handleSubmit()}
                  disabled={!label.trim() || !roleLabel || creating || rolesLoading}
                  className={cn(
                    'flex flex-1 items-center justify-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                    'hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                >
                  {creating ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : isEditing ? (
                    <Save size={16} />
                  ) : (
                    <Plus size={16} />
                  )}
                  {isEditing ? 'Save Changes' : 'Create Graph'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
