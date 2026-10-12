'use client';

import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { Lock, Users, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useMapsStore } from '@/stores/maps';
import { LayoutApiError } from '../lib/layouts-api';
import {
  accessSummary,
  mapsPermissionsApi,
  type MapsAccessItem,
  type MapsItemKind,
  type MapsPermissionsResponse,
} from '../lib/permissions-api';

function errorText(error: unknown, fallback: string): string {
  if (error instanceof LayoutApiError && error.errors.length) return error.errors.join('\n');
  return error instanceof Error ? error.message : fallback;
}

/** Settings → Maps access policy for the current workspace (admins only). */
export function useMapsPermissions(workspaceId: string, enabled: boolean) {
  const [data, setData] = useState<MapsPermissionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!enabled || !workspaceId) return;
    try {
      setData(await mapsPermissionsApi.list(workspaceId));
      setError(null);
    } catch (e) {
      setError(errorText(e, 'Could not load map access'));
    }
  }, [workspaceId, enabled]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const names = useMemo(
    () => new Map((data?.workspaces ?? []).map((w) => [w.id, w.name])),
    [data?.workspaces],
  );
  const find = useCallback(
    (kind: MapsItemKind, itemId: string) =>
      data?.items.find((item) => item.kind === kind && item.item_id === itemId),
    [data],
  );

  return { data, error, names, find, reload };
}

export type MapsPermissions = ReturnType<typeof useMapsPermissions>;

/** Access column cell: summary, and an editor when the user may change it. */
export function MapsAccessCell({
  workspaceId,
  kind,
  itemId,
  permissions,
}: {
  workspaceId: string;
  kind: MapsItemKind;
  itemId: string;
  permissions: MapsPermissions;
}) {
  const [open, setOpen] = useState(false);
  const item = permissions.find(kind, itemId);
  if (!item) return <span className="text-muted-foreground">—</span>;
  const summary = accessSummary(item, permissions.names);
  if (!item.editable) {
    const why = item.owner
      ? `Shared from ${permissions.names.get(item.owner) ?? item.owner}`
      : 'Deployment item: a platform superadmin sets where it is available';
    return (
      <span className="inline-flex min-w-0 items-center gap-1 text-muted-foreground" title={why}>
        <Lock size={12} className="shrink-0" aria-hidden />
        <span className="truncate">{item.owner ? why : summary}</span>
      </span>
    );
  }
  return (
    <>
      <button
        type="button"
        className="inline-flex min-w-0 max-w-full items-center gap-1 text-left underline-offset-2 hover:underline"
        onClick={() => setOpen(true)}
        title="Choose the workspaces that can use it"
      >
        <Users size={12} className="shrink-0" aria-hidden />
        <span className="truncate">{summary}</span>
      </button>
      {open && permissions.data ? (
        <MapsAccessModal
          workspaceId={workspaceId}
          item={item}
          data={permissions.data}
          onClose={() => setOpen(false)}
          onSaved={() => void permissions.reload()}
        />
      ) : null}
    </>
  );
}

function MapsAccessModal({
  workspaceId,
  item,
  data,
  onClose,
  onSaved,
}: {
  workspaceId: string;
  item: MapsAccessItem;
  data: MapsPermissionsResponse;
  onClose: () => void;
  onSaved: () => void;
}) {
  const titleId = useId();
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const [all, setAll] = useState(item.all_workspaces);
  const [selected, setSelected] = useState<Set<string>>(() => new Set(item.workspace_ids));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deployment = item.owner === '';
  // Workspaces already in the list that this user does not administer stay as they are.
  const others = item.workspace_ids.filter((id) => !data.workspaces.some((w) => w.id === id));

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const toggle = (id: string, on: boolean) =>
    setSelected((current) => {
      const next = new Set(current);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await mapsPermissionsApi.update(workspaceId, item.kind, item.item_id, {
        all_workspaces: all,
        workspace_ids: all ? [] : [...selected],
      });
      // The current workspace may have gained or lost the item.
      await loadLayouts(workspaceId, true);
      onSaved();
      onClose();
    } catch (e) {
      setError(errorText(e, 'Could not change access'));
      setBusy(false);
    }
  };

  return (
    <div className="maps-geojson-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <button type="button" className="maps-geojson-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="maps-geojson-modal__card maps-geojson-modal__card--form">
        <header className="maps-geojson-modal__header">
          <div>
            <h2 id={titleId} className="maps-geojson-modal__title">
              Access: {item.title}
            </h2>
            <p className="maps-geojson-modal__hint">
              {deployment
                ? 'Deployment item. Choose every workspace, or only some of them.'
                : 'Owned by this workspace. Share it read-only with other workspaces you administer.'}{' '}
              Members can still hide it in their own workspace.
            </p>
          </div>
          <button type="button" className="maps-geojson-modal__close" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </header>
        <div className="maps-geojson-modal__body maps-geojson-modal__body--stack">
          <fieldset className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`${titleId}-scope`}
                checked={all}
                disabled={!data.superadmin}
                onChange={() => setAll(true)}
              />
              All workspaces{!data.superadmin ? ' (superadmin only)' : ''}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name={`${titleId}-scope`} checked={!all} onChange={() => setAll(false)} />
              {deployment ? 'Only these workspaces' : 'This workspace, plus'}
            </label>
          </fieldset>
          {!all ? (
            <div className="max-h-64 space-y-1 overflow-y-auto border border-border p-2">
              {data.workspaces.length === 0 ? (
                <p className="text-sm text-muted-foreground">You do not administer other workspaces.</p>
              ) : null}
              {data.workspaces.map((w) => {
                const owner = w.id === item.owner;
                return (
                  <label key={w.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={owner || selected.has(w.id)}
                      disabled={owner}
                      onCheckedChange={(checked) => toggle(w.id, checked === true)}
                      aria-label={w.name}
                    />
                    <span className="truncate">{w.name}</span>
                    {owner ? <span className="text-xs text-muted-foreground">(owner)</span> : null}
                    {w.id === workspaceId && !owner ? (
                      <span className="text-xs text-muted-foreground">(this workspace)</span>
                    ) : null}
                  </label>
                );
              })}
              {others.length > 0 ? (
                <p className="pt-1 text-xs text-muted-foreground">
                  Also kept: {others.length} workspace{others.length === 1 ? '' : 's'} you do not administer.
                </p>
              ) : null}
            </div>
          ) : null}
          {error ? <p className="maps-form-field__error whitespace-pre-line">{error}</p> : null}
        </div>
        <footer className="maps-geojson-modal__footer">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void save()} disabled={busy}>
            Save access
          </Button>
        </footer>
      </div>
    </div>
  );
}
