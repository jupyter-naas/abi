'use client';

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MapsLayerEditorForm } from './maps-layer-editor-form';
import type { CustomLayerGroup } from '../lib/maps-layer-groups';

export function MapsNewLayerModal({
  open,
  onClose,
  workspaceId,
  takenIds,
  customLayerGroups,
  canEdit,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  takenIds: ReadonlySet<string>;
  customLayerGroups: ReadonlyArray<CustomLayerGroup>;
  canEdit: boolean;
  onCreated: (layerId: string) => void;
}) {
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    if (open) setFormKey((k) => k + 1);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="maps-geojson-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="maps-new-layer-title"
      data-testid="maps-new-layer-modal"
    >
      <button
        type="button"
        className="maps-geojson-modal__backdrop"
        aria-label="Close new layer dialog"
        onClick={onClose}
      />
      <div className="maps-geojson-modal__card maps-geojson-modal__card--form">
        <header className="maps-geojson-modal__header">
          <div>
            <h2 id="maps-new-layer-title" className="maps-geojson-modal__title">
              New layer
            </h2>
            <p className="maps-geojson-modal__hint">
              Import GeoJSON (this browser) or define a SPARQL query over workspace graphs (shared with all members).
            </p>
          </div>
          <button type="button" className="maps-geojson-modal__close" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </header>

        <div className="maps-geojson-modal__body">
          <MapsLayerEditorForm
            key={formKey}
            variant="modal"
            formId="maps-new-layer-form"
            workspaceId={workspaceId}
            takenIds={takenIds}
            customLayerGroups={customLayerGroups}
            canEdit={canEdit}
            workspaceLayout={null}
            onSavedWorkspace={(layout) => {
              onCreated(layout.id);
              onClose();
            }}
            onSavedGeoJson={(layerId) => {
              onCreated(layerId);
              onClose();
            }}
          />
        </div>

        <footer className="maps-geojson-modal__footer">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="maps-new-layer-form" data-testid="maps-new-layer-submit">
            Create layer
          </Button>
        </footer>
      </div>
    </div>
  );
}
