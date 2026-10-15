'use client';

import { useEffect, useId, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/input';
import { useMapsStore } from '@/stores/maps';
import {
  BASEMAP_PREVIEW_MAX_BYTES,
  BASEMAP_PREVIEW_TYPES,
  basemapsApi,
  type BasemapCategory,
  type BasemapPalette,
  type BasemapRenderer,
  type WorkspaceBasemap,
} from '../lib/basemaps-api';
import { LayoutApiError } from '../lib/layouts-api';

type Template = 'countries' | 'palette' | 'geojson' | 'tile';

const TEMPLATE_OPTIONS: { value: Template; label: string; hint: string }[] = [
  {
    value: 'countries',
    label: 'Countries (theme colors)',
    hint: 'Natural Earth country borders in the workspace theme, no street tiles.',
  },
  {
    value: 'palette',
    label: 'Countries (custom palette)',
    hint: 'Natural Earth countries with your own fill, border and ocean colors (light mode).',
  },
  {
    value: 'geojson',
    label: 'Custom GeoJSON',
    hint: 'Upload polygon boundaries (e.g. regions); no OSM underneath.',
  },
  {
    value: 'tile',
    label: 'Tile server',
    hint: 'An https:// XYZ tile template with {z} {x} {y} (and optional {s}).',
  },
];

const CATEGORY_OPTIONS: { value: BasemapCategory; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'organization', label: 'Organization' },
  { value: 'custom', label: 'Custom' },
];

const DEFAULT_PALETTE: Required<BasemapPalette> = {
  fill: '#e2e8f0',
  stroke: '#ffffff',
  background: '#ffffff',
};

function slugifyBasemapId(title: string): string {
  const slug = title
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
  return slug || 'basemap';
}

function templateOf(renderer: BasemapRenderer | undefined): Template {
  if (!renderer) return 'palette';
  if (renderer.kind === 'tile') return 'tile';
  if (renderer.kind === 'geojson') return 'geojson';
  return renderer.palette ? 'palette' : 'countries';
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof LayoutApiError && error.errors.length) return error.errors.join('\n');
  return error instanceof Error ? error.message : fallback;
}

/**
 * Create or edit a workspace basemap (Settings → Maps and File → New basemap).
 * Everything is saved to `/api/maps/basemaps`, preview image included.
 */
export function MapsNewBasemapModal({
  open,
  onClose,
  workspaceId,
  takenIds,
  basemap = null,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  takenIds: ReadonlySet<string>;
  /** Edit this basemap instead of creating one. */
  basemap?: WorkspaceBasemap | null;
  onCreated?: (basemapId: string) => void;
}) {
  const titleId = useId();
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const editing = basemap !== null;
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<BasemapCategory>('custom');
  const [order, setOrder] = useState(100);
  const [template, setTemplate] = useState<Template>('palette');
  const [palette, setPalette] = useState<Required<BasemapPalette>>(DEFAULT_PALETTE);
  const [geoJsonRaw, setGeoJsonRaw] = useState('');
  const [tileUrl, setTileUrl] = useState('');
  const [attribution, setAttribution] = useState('');
  const [preview, setPreview] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    const renderer = basemap?.renderer;
    setTitle(basemap?.title ?? '');
    setCategory(basemap?.category ?? 'custom');
    setOrder(basemap?.order ?? 100);
    setTemplate(templateOf(renderer));
    setPalette({
      ...DEFAULT_PALETTE,
      ...(renderer && renderer.kind !== 'tile' ? renderer.palette : {}),
    });
    setGeoJsonRaw(
      renderer?.kind === 'geojson' ? JSON.stringify(renderer.feature_collection, null, 2) : '',
    );
    setTileUrl(renderer?.kind === 'tile' ? renderer.url : '');
    setAttribution(renderer?.kind === 'tile' ? renderer.attribution ?? '' : '');
    setPreview(null);
    setError(null);
    setBusy(false);
  }, [open, basemap]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  const basemapId = useMemo(() => {
    if (basemap) return basemap.id;
    const base = slugifyBasemapId(title || 'basemap');
    if (!takenIds.has(base)) return base;
    let n = 2;
    while (takenIds.has(`${base}-${n}`)) n += 1;
    return `${base}-${n}`;
  }, [basemap, title, takenIds]);

  if (!open) return null;

  const buildRenderer = (): BasemapRenderer | string => {
    if (template === 'countries') return { kind: 'countries' };
    if (template === 'palette') {
      const previous = basemap?.renderer.kind === 'countries' ? basemap.renderer : undefined;
      return { kind: 'countries', palette, stroke_width: previous?.stroke_width ?? 0.5 };
    }
    if (template === 'tile') {
      const previous = basemap?.renderer.kind === 'tile' ? basemap.renderer : undefined;
      return {
        ...(previous ?? {}),
        kind: 'tile',
        url: tileUrl.trim(),
        attribution: attribution.trim(),
        ...(tileUrl.includes('{s}') && !previous?.subdomains ? { subdomains: ['a', 'b', 'c'] } : {}),
      };
    }
    try {
      const parsed = JSON.parse(geoJsonRaw) as GeoJSON.FeatureCollection;
      if (parsed.type !== 'FeatureCollection' || !Array.isArray(parsed.features)) {
        return 'Expected a GeoJSON FeatureCollection.';
      }
      return { kind: 'geojson', feature_collection: parsed };
    } catch {
      return 'Invalid GeoJSON JSON.';
    }
  };

  const onPickPreview = (file: File | null) => {
    setError(null);
    if (!file) return setPreview(null);
    if (!(BASEMAP_PREVIEW_TYPES as readonly string[]).includes(file.type)) {
      return setError('Preview must be PNG, JPEG, WebP or SVG.');
    }
    if (file.size > BASEMAP_PREVIEW_MAX_BYTES) {
      return setError(`Preview must be under ${BASEMAP_PREVIEW_MAX_BYTES / 1000} KB.`);
    }
    setPreview(file);
  };

  const onSubmit = async () => {
    const trimmed = title.trim();
    if (!trimmed) return setError('Title is required.');
    const renderer = buildRenderer();
    if (typeof renderer === 'string') return setError(renderer);
    setBusy(true);
    setError(null);
    try {
      await basemapsApi.save(workspaceId, basemapId, { title: trimmed, category, order, renderer });
      if (preview) await basemapsApi.uploadPreview(workspaceId, basemapId, preview);
      await loadLayouts(workspaceId, true);
      onCreated?.(basemapId);
      onClose();
    } catch (e) {
      setError(errorText(e, 'Could not save the basemap'));
      setBusy(false);
    }
  };

  const paletteField = (key: keyof BasemapPalette, label: string) => (
    <label className="maps-form-field maps-form-field--inline" key={key}>
      <span className="maps-form-field__label">{label}</span>
      <input
        type="color"
        value={palette[key]}
        onChange={(e) => setPalette((current) => ({ ...current, [key]: e.target.value }))}
        aria-label={label}
      />
    </label>
  );

  return (
    <div
      className="maps-geojson-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      data-testid="maps-new-basemap-modal"
    >
      <button type="button" className="maps-geojson-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="maps-geojson-modal__card maps-geojson-modal__card--form">
        <header className="maps-geojson-modal__header">
          <div>
            <h2 id={titleId} className="maps-geojson-modal__title">
              {editing ? `Edit basemap` : 'New basemap'}
            </h2>
            <p className="maps-geojson-modal__hint">
              Saved for every member of this workspace. Id: <code>{basemapId}</code>
            </p>
          </div>
          <button type="button" className="maps-geojson-modal__close" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </header>
        <div className="maps-geojson-modal__body maps-geojson-modal__body--stack">
          <label className="maps-form-field">
            <span className="maps-form-field__label">Name</span>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="EMEA footprint" />
          </label>
          <div className="flex gap-3">
            <label className="maps-form-field flex-1">
              <span className="maps-form-field__label">Picker column</span>
              <Select value={category} onChange={(e) => setCategory(e.target.value as BasemapCategory)}>
                {CATEGORY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </label>
            <label className="maps-form-field w-24">
              <span className="maps-form-field__label">Order</span>
              <Input
                type="number"
                value={order}
                onChange={(e) => setOrder(Number.parseInt(e.target.value, 10) || 0)}
              />
            </label>
          </div>
          <label className="maps-form-field">
            <span className="maps-form-field__label">Style</span>
            <Select value={template} onChange={(e) => setTemplate(e.target.value as Template)}>
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <span className="maps-form-field__hint">
              {TEMPLATE_OPTIONS.find((option) => option.value === template)?.hint}
            </span>
          </label>
          {template === 'palette' || template === 'geojson' ? (
            <div className="flex flex-wrap gap-4">
              {paletteField('fill', 'Land')}
              {paletteField('stroke', 'Borders')}
              {paletteField('background', 'Ocean')}
            </div>
          ) : null}
          {template === 'geojson' ? (
            <label className="maps-form-field">
              <span className="maps-form-field__label">GeoJSON</span>
              <textarea
                className="maps-geojson-textarea"
                rows={8}
                value={geoJsonRaw}
                onChange={(e) => setGeoJsonRaw(e.target.value)}
                placeholder='{ "type": "FeatureCollection", "features": [ … ] }'
              />
            </label>
          ) : null}
          {template === 'tile' ? (
            <>
              <label className="maps-form-field">
                <span className="maps-form-field__label">Tile URL</span>
                <Input
                  value={tileUrl}
                  onChange={(e) => setTileUrl(e.target.value)}
                  placeholder="https://tiles.example.com/{z}/{x}/{y}.png"
                />
              </label>
              <label className="maps-form-field">
                <span className="maps-form-field__label">Attribution</span>
                <Input value={attribution} onChange={(e) => setAttribution(e.target.value)} />
              </label>
            </>
          ) : null}
          <label className="maps-form-field">
            <span className="maps-form-field__label">
              Preview image {editing && basemap?.preview_content_type ? '(replace)' : ''}
            </span>
            <input
              type="file"
              accept={BASEMAP_PREVIEW_TYPES.join(',')}
              onChange={(e) => onPickPreview(e.target.files?.[0] ?? null)}
            />
            <span className="maps-form-field__hint">PNG, JPEG, WebP or SVG, square, up to 512 KB.</span>
          </label>
          {error ? <p className="maps-form-field__error whitespace-pre-line">{error}</p> : null}
        </div>
        <footer className="maps-geojson-modal__footer">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void onSubmit()} disabled={busy}>
            {editing ? 'Save changes' : 'Save basemap'}
          </Button>
        </footer>
      </div>
    </div>
  );
}
