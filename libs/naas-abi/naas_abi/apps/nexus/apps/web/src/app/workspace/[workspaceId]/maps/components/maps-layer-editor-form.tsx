'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, Loader2, Play, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Select, Textarea } from '@/components/ui/input';
import type { MapsLayerGroupId } from '../lib/datasets';
import { MapsIconGallery } from './maps-icon-gallery';
import {
  downloadLayerTemplate,
  parseGeoJsonLayerInput,
  saveImportedMapLayer,
  slugifyLayerSlug,
  validateLayerSlug,
} from '../lib/maps-imported-layers';
import {
  BUILTIN_LAYER_GROUPS,
  CREATE_LAYER_GROUP_VALUE,
  resolveLayerGroupSelection,
  type CustomLayerGroup,
} from '../lib/maps-layer-groups';
import {
  blankLayout,
  LayoutApiError,
  layoutPreviewPinRows,
  layoutsApi,
  type LayoutDraft,
  type LayoutPreview,
} from '../lib/layouts-api';
import type { WorkspaceMapLayout } from '../lib/layouts';
import { setWorkspaceLayerGroupId } from '../lib/maps-workspace-layer-meta';
import { useWorkspaceGraphs } from '../lib/use-workspace-graphs';
import { ALL_LAYERS_ID } from '../lib/layouts';

export type LayerDataSource = 'geojson' | 'sparql';

const LAYOUT_ID = /^[a-z0-9][a-z0-9-]{0,47}$/;

function layoutSlugError(slug: string, isNew: boolean, takenIds: ReadonlySet<string>): string | null {
  if (!isNew) return null;
  if (!slug) return null;
  if (!LAYOUT_ID.test(slug)) {
    return 'Lowercase letters, digits and dashes, starting with a letter or digit (max 48).';
  }
  if (slug === ALL_LAYERS_ID || takenIds.has(slug)) return 'This slug is already used by another layer.';
  return null;
}

export function MapsLayerEditorForm({
  workspaceId,
  takenIds,
  customLayerGroups,
  canEdit,
  workspaceLayout,
  initialGroupId = 'custom',
  variant,
  formId = 'maps-layer-editor-form',
  onSavedWorkspace,
  onSavedGeoJson,
}: {
  workspaceId: string;
  takenIds: ReadonlySet<string>;
  customLayerGroups: ReadonlyArray<CustomLayerGroup>;
  canEdit: boolean;
  /** When set, SPARQL edit mode (GeoJSON tab hidden). */
  workspaceLayout: WorkspaceMapLayout | null;
  initialGroupId?: MapsLayerGroupId;
  variant: 'modal' | 'page';
  formId?: string;
  onSavedWorkspace: (layout: WorkspaceMapLayout) => void;
  onSavedGeoJson: (layerId: string) => void;
}) {
  const isEdit = workspaceLayout !== null;
  const isNew = !isEdit;
  const readOnly = !canEdit;
  const graphs = useWorkspaceGraphs(workspaceId);

  const [source, setSource] = useState<LayerDataSource>(isEdit ? 'sparql' : 'geojson');
  const [slug, setSlug] = useState(workspaceLayout?.id ?? '');
  const [slugTouched, setSlugTouched] = useState(false);
  const [draft, setDraft] = useState<LayoutDraft>(() => {
    if (!workspaceLayout) return blankLayout();
    const { id: _id, ...rest } = workspaceLayout;
    return rest;
  });
  const [groupSelection, setGroupSelection] = useState<string>(initialGroupId);
  const [newGroupName, setNewGroupName] = useState('');
  const [geoJsonText, setGeoJsonText] = useState('');
  const [featureCount, setFeatureCount] = useState<number | null>(null);
  const [preview, setPreview] = useState<LayoutPreview | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState<'save' | 'preview' | null>(null);

  const creatingGroup = groupSelection === CREATE_LAYER_GROUP_VALUE;

  const setDraftField = <K extends keyof LayoutDraft>(key: K, value: LayoutDraft[K]) => {
    setDraft((d) => ({ ...d, [key]: value }));
  };

  useEffect(() => {
    if (slugTouched || isEdit || !draft.title.trim()) return;
    setSlug(slugifyLayerSlug(draft.title));
  }, [draft.title, slugTouched, isEdit]);

  const slugErr = useMemo(
    () => (source === 'geojson' ? validateLayerSlug(slug, takenIds) : layoutSlugError(slug, isNew, takenIds)),
    [source, slug, takenIds, isNew],
  );

  const validateGeoJson = useCallback((text: string) => {
    const parsed = parseGeoJsonLayerInput(text);
    if (parsed.ok) {
      setFeatureCount(parsed.featureCount);
      return null;
    }
    setFeatureCount(null);
    return parsed.error;
  }, []);

  const onPickFile = async (file: File | null) => {
    if (!file) return;
    try {
      const text = await file.text();
      setGeoJsonText(text);
      const geoError = validateGeoJson(text);
      setErrors(geoError ? [geoError] : []);
    } catch {
      setErrors(['Could not read the file.']);
    }
  };

  const runPreview = async () => {
    setBusy('preview');
    setErrors([]);
    setPreview(null);
    try {
      const result = await layoutsApi.preview(workspaceId, draft);
      if (result.errors.length) setErrors(result.errors);
      else setPreview(result);
    } catch (e) {
      setErrors([e instanceof LayoutApiError ? e.message : 'Could not run the query']);
    } finally {
      setBusy(null);
    }
  };

  const persistGroup = (layerId: string) => {
    const resolved = resolveLayerGroupSelection(workspaceId, groupSelection, newGroupName);
    if (resolved.groupId) setWorkspaceLayerGroupId(workspaceId, layerId, resolved.groupId);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextErrors: string[] = [];
    if (!draft.title.trim()) nextErrors.push('Title is required.');
    if (slugErr) nextErrors.push(slugErr);
    if (creatingGroup) {
      const g = resolveLayerGroupSelection(workspaceId, groupSelection, newGroupName);
      if (g.error) nextErrors.push(g.error);
    }

    if (source === 'geojson') {
      const geoError = validateGeoJson(geoJsonText);
      if (geoError) nextErrors.push(geoError);
    } else if (!draft.query.trim()) {
      nextErrors.push('SPARQL query is required.');
    }

    if (nextErrors.length) {
      setErrors(nextErrors);
      return;
    }

    setBusy('save');
    setErrors([]);
    try {
      if (source === 'geojson') {
        const parsed = parseGeoJsonLayerInput(geoJsonText);
        if (!parsed.ok) {
          setErrors([parsed.error]);
          return;
        }
        const resolved = resolveLayerGroupSelection(workspaceId, groupSelection, newGroupName);
        if (resolved.error || !resolved.groupId) {
          setErrors([resolved.error ?? 'Could not assign a layer group.']);
          return;
        }
        saveImportedMapLayer(workspaceId, {
          id: slug.trim(),
          title: draft.title.trim(),
          description: draft.description.trim(),
          icon: draft.icon,
          color: draft.color,
          order: draft.order,
          groupId: resolved.groupId,
          featureCollection: parsed.collection,
        });
        onSavedGeoJson(slug.trim());
        return;
      }

      if (!canEdit) {
        setErrors(['Only workspace owners and admins can save SPARQL layers.']);
        return;
      }

      const layoutId = isNew ? slug.trim() : workspaceLayout!.id;
      const saved = await layoutsApi.save(workspaceId, layoutId, {
        ...draft,
        title: draft.title.trim(),
        icon: draft.icon,
        color: draft.color,
      });
      persistGroup(saved.id);
      onSavedWorkspace(saved);
    } catch (e) {
      setErrors(
        e instanceof LayoutApiError && e.errors.length
          ? e.errors
          : [e instanceof Error ? e.message : 'Could not save the layer'],
      );
    } finally {
      setBusy(null);
    }
  };

  const canSubmit =
    busy === null
    && draft.title.trim()
    && (source === 'geojson'
      ? Boolean(geoJsonText.trim()) && !slugErr
      : Boolean(draft.query.trim()) && (isNew ? Boolean(slug && !slugErr) : true));

  return (
    <form id={formId} className="maps-new-layer-form" onSubmit={(e) => void submit(e)}>
      {errors.length > 0 && (
        <ul className="maps-new-layer-form__errors" data-testid="maps-layer-editor-errors">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}

      {!isEdit ? (
        <div className="maps-layer-source-tabs" role="tablist" aria-label="Layer data source">
          <button
            type="button"
            role="tab"
            aria-selected={source === 'geojson'}
            className={source === 'geojson' ? 'maps-layer-source-tabs__btn--active' : undefined}
            onClick={() => setSource('geojson')}
          >
            GeoJSON
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={source === 'sparql'}
            disabled={!canEdit}
            title={canEdit ? undefined : 'SPARQL layers require workspace admin'}
            className={source === 'sparql' ? 'maps-layer-source-tabs__btn--active' : undefined}
            onClick={() => canEdit && setSource('sparql')}
          >
            SPARQL
          </button>
        </div>
      ) : null}

      {source === 'sparql' && !canEdit ? (
        <p className="maps-new-layer-form__hint-block">
          SPARQL workspace layers can only be created or edited by workspace owners and admins.
        </p>
      ) : null}

      <label className="maps-new-layer-form__field">
        <span>Title</span>
        <Input
          value={draft.title}
          disabled={readOnly}
          onChange={(e) => setDraftField('title', e.target.value)}
          placeholder="Sites, offices, assets…"
          data-testid="maps-new-layer-title"
        />
      </label>

      {isNew ? (
        <label className="maps-new-layer-form__field">
          <span>Layer slug</span>
          <Input
            value={slug}
            disabled={readOnly}
            onChange={(e) => {
              setSlugTouched(true);
              setSlug(e.target.value.trim().toLowerCase());
            }}
            placeholder="my-sites"
            spellCheck={false}
            className="font-mono"
            data-testid="maps-new-layer-slug"
          />
          <span className="maps-new-layer-form__hint-block">
            Derived from the title; used in the map URL and layer list. You can edit it before saving.
          </span>
          {slugErr ? <span className="maps-new-layer-form__field-error">{slugErr}</span> : null}
        </label>
      ) : null}

      <label className="maps-new-layer-form__field">
        <span>Description</span>
        <Input
          value={draft.description}
          disabled={readOnly}
          onChange={(e) => setDraftField('description', e.target.value)}
          placeholder="Optional"
        />
      </label>

      <label className="maps-new-layer-form__field">
        <span>Layer group</span>
        <Select
          value={groupSelection}
          disabled={readOnly}
          onChange={(e) => setGroupSelection(e.target.value)}
          data-testid="maps-new-layer-group"
        >
          {BUILTIN_LAYER_GROUPS.map((group) => (
            <option key={group.id} value={group.id}>
              {group.label}
            </option>
          ))}
          {customLayerGroups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.label}
            </option>
          ))}
          <option value={CREATE_LAYER_GROUP_VALUE}>Create new group…</option>
        </Select>
      </label>

      {creatingGroup ? (
        <label className="maps-new-layer-form__field">
          <span>New group name</span>
          <Input
            value={newGroupName}
            disabled={readOnly}
            onChange={(e) => setNewGroupName(e.target.value)}
            placeholder="Operations, Exercises…"
            data-testid="maps-new-layer-group-name"
          />
        </label>
      ) : null}

      <div className="maps-new-layer-form__row">
        <label className="maps-new-layer-form__field">
          <span>Pin colour</span>
          <Input
            type="color"
            value={draft.color}
            disabled={readOnly}
            onChange={(e) => setDraftField('color', e.target.value)}
            className="maps-new-layer-form__color"
          />
        </label>
      </div>

      <div className="maps-new-layer-form__field">
        <span>Icon</span>
        <MapsIconGallery
          value={draft.icon}
          onChange={(icon) => setDraftField('icon', icon)}
        />
      </div>

      {source === 'geojson' ? (
        <div className="maps-new-layer-form__geo">
          <div className="maps-new-layer-form__geo-head">
            <span>GeoJSON</span>
            <div className="maps-new-layer-form__geo-actions">
              <Button type="button" variant="secondary" size="sm" onClick={() => downloadLayerTemplate()}>
                <Download size={14} /> Template
              </Button>
              <label className="maps-new-layer-form__file">
                <Upload size={14} /> Import file
                <input
                  type="file"
                  accept=".geojson,.json,application/geo+json,application/json"
                  className="sr-only"
                  disabled={readOnly}
                  onChange={(e) => void onPickFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </div>
          </div>
          <Textarea
            value={geoJsonText}
            disabled={readOnly}
            onChange={(e) => {
              setGeoJsonText(e.target.value);
              if (e.target.value.trim()) validateGeoJson(e.target.value);
              else setFeatureCount(null);
            }}
            rows={variant === 'modal' ? 10 : 12}
            spellCheck={false}
            className="font-mono text-xs"
            placeholder={'Paste a FeatureCollection or { "pins": [ … ] }…'}
            data-testid="maps-new-layer-geojson"
          />
          {featureCount != null ? (
            <p className="maps-new-layer-form__feature-count">
              {featureCount} point feature{featureCount === 1 ? '' : 's'} ready
            </p>
          ) : null}
          {variant === 'modal' ? (
            <p className="maps-new-layer-form__hint-block">
              GeoJSON layers are stored in this browser only. Use SPARQL for a layer shared with the workspace.
            </p>
          ) : null}
        </div>
      ) : (
        <>
          <div className="maps-new-layer-form__field">
            <span>Graphs</span>
            <p className="maps-new-layer-form__hint-block">
              Limit the query to specific graphs, or leave none selected to search every graph this workspace can read.
            </p>
            {graphs === null ? (
              <p className="text-xs text-muted-foreground">Loading graphs…</p>
            ) : graphs.length === 0 ? (
              <p className="text-xs text-muted-foreground">This workspace cannot read any graph yet.</p>
            ) : (
              <div className="maps-new-layer-form__graphs">
                {graphs.map((g) => (
                  <Checkbox
                    key={g.uri}
                    label={g.label}
                    title={g.uri}
                    disabled={readOnly}
                    checked={draft.graphs.includes(g.uri)}
                    onCheckedChange={(on) =>
                      setDraftField(
                        'graphs',
                        on ? [...draft.graphs, g.uri] : draft.graphs.filter((u) => u !== g.uri),
                      )
                    }
                  />
                ))}
              </div>
            )}
          </div>

          <div className="maps-new-layer-form__field">
            <div className="maps-new-layer-form__geo-head">
              <span>SPARQL query</span>
              {canEdit && !readOnly ? (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={busy !== null || !draft.query.trim()}
                  onClick={() => void runPreview()}
                >
                  {busy === 'preview' ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                  Run
                </Button>
              ) : null}
            </div>
            <Textarea
              value={draft.query}
              disabled={readOnly}
              spellCheck={false}
              rows={variant === 'modal' ? 10 : 14}
              onChange={(e) => setDraftField('query', e.target.value)}
              className="font-mono text-xs"
              aria-label="SPARQL query"
            />
            {preview ? (
              <div className="mt-2 text-sm">
                <p className="font-medium">{preview.count} pin{preview.count === 1 ? '' : 's'}</p>
                {preview.features.length > 0 ? (
                  <ul className="mt-1 max-h-36 overflow-auto text-xs text-muted-foreground">
                    {layoutPreviewPinRows(preview).slice(0, 15).map((pin) => (
                      <li key={pin.id} className="truncate">
                        <span className="text-foreground">{pin.label}</span> · {pin.lat.toFixed(4)}, {pin.lng.toFixed(4)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
            <p className="maps-new-layer-form__hint-block">
              SELECT must project ?label ?lat ?lng. Optional: ?uri ?detail ?graph.
            </p>
          </div>
        </>
      )}

      {variant === 'page' ? (
        <div className="flex flex-wrap gap-2 pt-2">
          <Button type="submit" disabled={!canSubmit || readOnly}>
            {busy === 'save' ? <Loader2 size={14} className="animate-spin" /> : null}
            Save layer
          </Button>
        </div>
      ) : null}

    </form>
  );
}
