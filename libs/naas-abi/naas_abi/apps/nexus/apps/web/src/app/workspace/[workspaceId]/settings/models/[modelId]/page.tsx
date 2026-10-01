'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { ArrowLeft } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input, Textarea } from '@/components/ui/input';
import {
  SettingsField,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
} from '@/components/settings/settings-ui';

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
    <div className="space-y-6">
      <div>
        <Button variant="secondary" onClick={() => router.push(backToList)}>
          <ArrowLeft size={16} />
          Back to models
        </Button>
      </div>

      {loading ? (
        <SettingsLoading label="Loading model…" />
      ) : error && !model ? (
        <div className="space-y-4">
          <SettingsNotice tone="error">{error}</SettingsNotice>
          <Button variant="secondary" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      ) : model ? (
        <div className="space-y-6">
          <SettingsPageHeader
            leading={
              <div className="flex h-10 w-10 flex-none items-center justify-center overflow-hidden border border-border bg-muted">
                {form.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={form.image} alt={model.name ?? model.canonical_id} className="h-full w-full object-contain" />
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </div>
            }
            title={model.name ?? model.canonical_id}
            description={<span className="font-mono text-xs">{model.canonical_id}</span>}
            actions={
              <Badge variant={model.configured ? 'primary' : 'neutral'}>
                {model.configured ? 'Configured' : 'Not configured'}
              </Badge>
            }
          />

          <SettingsSection title="Display properties">
            <div className="space-y-4">
              <SettingsField label="Name">
                <Input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="Model display name"
                />
              </SettingsField>

              <SettingsField label="Description">
                <Textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={4}
                  className="resize-y"
                  placeholder="Short description shown in the model list"
                />
              </SettingsField>

              <SettingsField label="Image URL">
                <Input
                  type="text"
                  value={form.image}
                  onChange={(e) => setForm((f) => ({ ...f, image: e.target.value }))}
                  placeholder="https://… or a relative asset path"
                />
              </SettingsField>

              <SettingsField label="Context window">
                <Input
                  type="number"
                  min={0}
                  value={form.context_window}
                  onChange={(e) => setForm((f) => ({ ...f, context_window: e.target.value }))}
                  placeholder="e.g. 200000"
                />
                {contextWindowInvalid && <p className="text-xs text-destructive">Context window must be a number.</p>}
              </SettingsField>
            </div>
          </SettingsSection>

          <SettingsSection title="Source identity (read-only)">
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <ReadOnly label="Model ID" value={model.model_id} mono />
              <ReadOnly label="Provider" value={model.provider} />
              <ReadOnly label="Provider ID" value={model.provider_id} />
              <ReadOnly label="Status" value={model.configured ? 'Configured' : 'Not configured'} />
              <ReadOnly label="Module path" value={model.module_path} mono wide />
            </dl>
          </SettingsSection>

          <div className="flex items-center gap-3 border-t border-border pt-5">
            <Button onClick={() => void handleSave()} disabled={!isDirty || saving || contextWindowInvalid}>
              {saving ? 'Saving…' : 'Save changes'}
            </Button>
            <Button variant="secondary" onClick={handleReset} disabled={!isDirty || saving}>
              Reset
            </Button>
            {error && <span className="text-sm text-destructive">{error}</span>}
            {!error && savedAt && !isDirty && <span className="text-sm text-primary">Saved.</span>}
          </div>
        </div>
      ) : null}
    </div>
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
