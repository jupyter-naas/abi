'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { MapsLayerEditorForm } from './maps-layer-editor-form';

export function MapsNewLayerModal({
  open,
  onClose,
  workspaceId,
  takenIds,
  layerGroups,
  canEdit,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  takenIds: ReadonlySet<string>;
  layerGroups: readonly string[];
  canEdit: boolean;
  onCreated: (layerId: string) => void;
}) {
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    if (open) setFormKey((k) => k + 1);
  }, [open]);

  if (!open) return null;

  return (
    <Dialog
      size="xl"
      title="New layer"
      description="Import GeoJSON (this browser) or define a SPARQL query over workspace graphs (shared with all members)."
      onClose={onClose}
      onSubmit={() => document.querySelector<HTMLFormElement>('#maps-new-layer-form')?.requestSubmit()}
      data-testid="maps-new-layer-modal"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="maps-new-layer-form" data-testid="maps-new-layer-submit">
            Create layer
          </Button>
        </>
      }
    >
      <MapsLayerEditorForm
        key={formKey}
        variant="modal"
        formId="maps-new-layer-form"
        workspaceId={workspaceId}
        takenIds={takenIds}
        layerGroups={layerGroups}
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
    </Dialog>
  );
}
