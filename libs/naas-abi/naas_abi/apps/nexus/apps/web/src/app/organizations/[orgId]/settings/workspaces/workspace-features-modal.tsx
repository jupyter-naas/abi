'use client';

import { useEffect, useMemo, useState } from 'react';
import { RotateCcw, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModalBackdrop } from '@/components/ui/dialogs';
import {
  choicesFromOverrides,
  configurableFeatures,
  overridesFromChoices,
  WorkspaceFeaturesTable,
  type FeatureChoice,
  type WorkspaceFeatureCatalog,
} from './workspace-features-table';

export type { WorkspaceFeatureCatalog } from './workspace-features-table';

export type OverridesSource = 'database' | 'deployment' | null;

/**
 * Workspace features (Organization Settings > Workspaces > Features): the
 * per-workspace overrides of the role defaults, like
 * ``nexus_config.feature_flags.workspace_overrides`` in the config. Saving
 * stores them on the workspace and they replace the config entry; "Use
 * config" drops them so the config applies again.
 */
export function WorkspaceFeaturesModal({
  open,
  workspaceName,
  overrides,
  source,
  catalog,
  canEdit,
  onClose,
  onSave,
}: {
  open: boolean;
  workspaceName: string;
  overrides: Record<string, boolean>;
  source: OverridesSource;
  catalog: WorkspaceFeatureCatalog | null;
  canEdit: boolean;
  onClose: () => void;
  /** ``null`` restores the config overrides. Rejects with the message to show. */
  onSave: (overrides: Record<string, boolean> | null) => Promise<void>;
}) {
  const [draft, setDraft] = useState<Record<string, FeatureChoice>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setDraft(choicesFromOverrides(overrides));
    setSaving(false);
    setError('');
  }, [open, overrides]);

  const features = useMemo(() => configurableFeatures(catalog), [catalog]);

  const save = async (next: Record<string, boolean> | null) => {
    setSaving(true);
    setError('');
    try {
      await onSave(next);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to save the features');
      setSaving(false);
    }
  };

  const sourceText =
    source === 'database'
      ? 'Overrides saved in the app. They replace the config entry for this workspace.'
      : source === 'deployment'
        ? 'Overrides from the deployment config. Saving here moves them to the app.'
        : 'No overrides: every feature follows the role defaults.';

  return (
    <ModalBackdrop
      open={open}
      onClose={saving ? () => undefined : onClose}
      widthClassName="max-w-2xl"
    >
      <div className="flex max-h-[85vh] flex-col border border-border bg-background shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border p-6 pb-4">
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-foreground">
              Features · {workspaceName}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">{sourceText}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            disabled={saving}
            aria-label="Close"
          >
            <X size={16} />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-2">
          {!catalog ? (
            <p className="py-6 text-sm text-muted-foreground">Loading features...</p>
          ) : (
            <WorkspaceFeaturesTable
              catalog={catalog}
              choices={draft}
              disabled={!canEdit || saving}
              onChange={(feature, choice) =>
                setDraft((current) => ({ ...current, [feature]: choice }))
              }
            />
          )}
        </div>

        {error && <p className="px-6 pt-3 text-sm text-destructive">{error}</p>}

        <div className="flex items-center justify-between gap-2 border-t border-border p-6 pt-4">
          <div>
            {canEdit && source === 'database' && (
              <Button variant="ghost" onClick={() => void save(null)} disabled={saving}>
                <RotateCcw size={14} />
                Use config
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            {canEdit && (
              <Button onClick={() => void save(overridesFromChoices(draft, features))} disabled={saving || !catalog}>
                {saving ? 'Saving...' : 'Save'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}
