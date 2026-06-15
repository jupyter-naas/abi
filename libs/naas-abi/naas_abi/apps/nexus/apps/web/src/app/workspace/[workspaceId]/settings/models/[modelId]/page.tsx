'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';

const getApiBase = () => getApiUrl();

type Model = {
  canonical_id: string;
  model_id: string;
  provider: string;
  provider_id: string;
  module_path: string;
  configured: boolean;
  name: string | null;
  description: string | null;
  image: string | null;
  context_window: number | null;
};

// Display properties the user is allowed to override from the frontend. These
// map 1:1 to the backend ModelUpdate schema / SYNCABLE_MODEL_FIELDS.
type EditableFields = {
  name: string;
  description: string;
  image: string;
  context_window: string;
};

const emptyForm: EditableFields = {
  name: '',
  description: '',
  image: '',
  context_window: '',
};

function toForm(model: Model): EditableFields {
  return {
    name: model.name ?? '',
    description: model.description ?? '',
    image: model.image ?? '',
    context_window:
      model.context_window === null || model.context_window === undefined
        ? ''
        : String(model.context_window),
  };
}

export default function ModelDetailPage() {
  const router = useRouter();
  const params = useParams();
  const workspaceId = (params?.workspaceId as string | undefined) ?? '';
  const modelId = useMemo(() => {
    const raw = params?.modelId;
    return typeof raw === 'string' ? decodeURIComponent(raw) : '';
  }, [params]);

  const [model, setModel] = useState<Model | null>(null);
  const [form, setForm] = useState<EditableFields>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const backToList = `/workspace/${workspaceId}/settings/models`;

  const load = useCallback(async () => {
    if (!modelId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(
        `${getApiBase()}/api/providers/models/${encodeURIComponent(modelId)}`,
      );
      if (!res.ok) {
        throw new Error(
          res.status === 404
            ? `Model "${modelId}" was not found.`
            : `Failed to load model (${res.status}).`,
        );
      }
      const data: Model = await res.json();
      setModel(data);
      setForm(toForm(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Compute the patch body: only fields that differ from the loaded model are
  // sent (and thus recorded as frontend overrides by the backend).
  const dirtyPatch = useMemo(() => {
    if (!model) return {};
    const patch: Record<string, string | number | null> = {};
    const original = toForm(model);

    if (form.name !== original.name) patch.name = form.name.trim() || null;
    if (form.description !== original.description)
      patch.description = form.description.trim() || null;
    if (form.image !== original.image) patch.image = form.image.trim() || null;
    if (form.context_window !== original.context_window) {
      const trimmed = form.context_window.trim();
      patch.context_window = trimmed === '' ? null : Number(trimmed);
    }
    return patch;
  }, [form, model]);

  const isDirty = Object.keys(dirtyPatch).length > 0;
  const contextWindowInvalid =
    form.context_window.trim() !== '' &&
    !Number.isFinite(Number(form.context_window.trim()));

  const handleSave = useCallback(async () => {
    if (!model || !isDirty || contextWindowInvalid) return;
    setSaving(true);
    setError(null);
    try {
      const res = await authFetch(
        `${getApiBase()}/api/providers/models/${encodeURIComponent(model.canonical_id)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(dirtyPatch),
        },
      );
      if (!res.ok) {
        throw new Error(`Failed to save changes (${res.status}).`);
      }
      const data: Model = await res.json();
      setModel(data);
      setForm(toForm(data));
      setSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [model, isDirty, contextWindowInvalid, dirtyPatch]);

  const handleReset = useCallback(() => {
    if (model) setForm(toForm(model));
    setSavedAt(null);
  }, [model]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <button
        type="button"
        onClick={() => router.push(backToList)}
        className="mb-6 text-sm text-muted-foreground hover:text-foreground"
      >
        ← Back to models
      </button>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading model…</p>
      ) : error && !model ? (
        <div className="space-y-4">
          <p className="text-sm text-destructive">{error}</p>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Retry
          </button>
        </div>
      ) : model ? (
        <div className="space-y-8">
          <header className="flex items-center gap-4">
            <div className="flex h-12 w-12 flex-none items-center justify-center overflow-hidden rounded-lg border bg-muted">
              {form.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={form.image}
                  alt={model.name ?? model.canonical_id}
                  className="h-full w-full object-contain"
                />
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold">
                {model.name ?? model.canonical_id}
              </h1>
              <p className="truncate font-mono text-xs text-muted-foreground">
                {model.canonical_id}
              </p>
            </div>
          </header>

          {/* Editable display properties */}
          <section className="space-y-5">
            <h2 className="text-sm font-medium text-muted-foreground">
              Display properties
            </h2>

            <Field label="Name">
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Model display name"
              />
            </Field>

            <Field label="Description">
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                rows={4}
                className="w-full resize-y rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Short description shown in the model list"
              />
            </Field>

            <Field label="Image URL">
              <input
                type="text"
                value={form.image}
                onChange={(e) => setForm((f) => ({ ...f, image: e.target.value }))}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="https://… or a relative asset path"
              />
            </Field>

            <Field label="Context window">
              <input
                type="number"
                min={0}
                value={form.context_window}
                onChange={(e) =>
                  setForm((f) => ({ ...f, context_window: e.target.value }))
                }
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="e.g. 200000"
              />
              {contextWindowInvalid && (
                <p className="mt-1 text-xs text-destructive">
                  Context window must be a number.
                </p>
              )}
            </Field>
          </section>

          {/* Read-only structural identity (always sourced from the Python module) */}
          <section className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">
              Source identity (read-only)
            </h2>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <ReadOnly label="Model ID" value={model.model_id} mono />
              <ReadOnly label="Provider" value={model.provider} />
              <ReadOnly label="Provider ID" value={model.provider_id} />
              <ReadOnly
                label="Status"
                value={model.configured ? 'Configured' : 'Not configured'}
              />
              <ReadOnly label="Module path" value={model.module_path} mono wide />
            </dl>
          </section>

          <footer className="flex items-center gap-3 border-t pt-5">
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={!isDirty || saving || contextWindowInvalid}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            <button
              type="button"
              onClick={handleReset}
              disabled={!isDirty || saving}
              className="rounded-md border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
            >
              Reset
            </button>
            {error && <span className="text-sm text-destructive">{error}</span>}
            {!error && savedAt && !isDirty && (
              <span className="text-sm text-muted-foreground">Saved.</span>
            )}
          </footer>
        </div>
      ) : null}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}

function ReadOnly({
  label,
  value,
  mono,
  wide,
}: {
  label: string;
  value: string;
  mono?: boolean;
  wide?: boolean;
}) {
  return (
    <div className={wide ? 'sm:col-span-2' : undefined}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`mt-0.5 break-all text-sm ${mono ? 'font-mono' : ''}`}>
        {value}
      </dd>
    </div>
  );
}
