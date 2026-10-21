'use client';

import { useEffect, useMemo, useState } from 'react';
import { RotateCcw, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ModalBackdrop } from '@/components/ui/dialogs';
import { featureLabel } from '../lib/feature-labels';

export interface WorkspaceFeatureCatalog {
  /** Deployment catalog (enabled_features). */
  catalog: string[];
  /** Always on, not editable per workspace (Settings). */
  pinned: string[];
  roles: string[];
  /** Role defaults for this organization (deployment baseline + org overlay). */
  role_baseline: Record<string, string[]>;
}

export type OverridesSource = 'database' | 'deployment' | null;

type Choice = 'default' | 'on' | 'off';

const CHOICES: { id: Choice; label: string }[] = [
  { id: 'default', label: 'Default' },
  { id: 'on', label: 'On' },
  { id: 'off', label: 'Off' },
];

const ROLE_LABELS: Record<string, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
};

function rolesText(roles: string[]): string {
  return roles.length ? roles.map((role) => ROLE_LABELS[role] || role).join(', ') : 'No role';
}

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
  const [draft, setDraft] = useState<Record<string, Choice>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setDraft(
      Object.fromEntries(
        Object.entries(overrides).map(([key, on]) => [key, on ? 'on' : 'off'] as const)
      )
    );
    setSaving(false);
    setError('');
  }, [open, overrides]);

  const features = useMemo(
    () => (catalog ? catalog.catalog.filter((key) => !catalog.pinned.includes(key)) : []),
    [catalog]
  );

  const defaultRoles = (feature: string): string[] =>
    catalog ? catalog.roles.filter((role) => catalog.role_baseline[role]?.includes(feature)) : [];

  const resultText = (feature: string): string => {
    const choice = draft[feature] ?? 'default';
    if (choice === 'on') return 'Every role';
    if (choice === 'off') return 'Hidden';
    return rolesText(defaultRoles(feature));
  };

  const draftOverrides = (): Record<string, boolean> =>
    Object.fromEntries(
      Object.entries(draft)
        .filter(([key, choice]) => choice !== 'default' && features.includes(key))
        .map(([key, choice]) => [key, choice === 'on'])
    );

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
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Feature</th>
                  <th className="py-2 pr-3 font-medium">Role default</th>
                  <th className="py-2 pr-3 font-medium">Override</th>
                  <th className="py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody>
                {features.map((feature) => {
                  const choice = draft[feature] ?? 'default';
                  return (
                    <tr key={feature} className="border-t border-border">
                      <td className="py-2 pr-3 font-medium text-foreground">
                        {featureLabel(feature)}
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">
                        {rolesText(defaultRoles(feature))}
                      </td>
                      <td className="py-2 pr-3">
                        <div
                          className="inline-flex border border-border"
                          role="radiogroup"
                          aria-label={`${featureLabel(feature)} override`}
                        >
                          {CHOICES.map((option) => (
                            <button
                              key={option.id}
                              type="button"
                              role="radio"
                              aria-checked={choice === option.id}
                              disabled={!canEdit || saving}
                              onClick={() =>
                                setDraft((current) => ({ ...current, [feature]: option.id }))
                              }
                              className={cn(
                                'px-2.5 py-1 text-xs transition-colors disabled:cursor-not-allowed',
                                choice === option.id
                                  ? option.id === 'off'
                                    ? 'bg-destructive text-destructive-foreground'
                                    : 'bg-primary text-primary-foreground'
                                  : 'text-muted-foreground hover:bg-muted'
                              )}
                            >
                              {option.label}
                            </button>
                          ))}
                        </div>
                      </td>
                      <td
                        className={cn(
                          'py-2',
                          choice === 'off' ? 'text-muted-foreground line-through' : 'text-foreground'
                        )}
                      >
                        {resultText(feature)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {catalog && catalog.pinned.length > 0 && (
            <p className="py-3 text-xs text-muted-foreground">
              {catalog.pinned.map(featureLabel).join(', ')} always follows the role defaults.
            </p>
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
              <Button onClick={() => void save(draftOverrides())} disabled={saving || !catalog}>
                {saving ? 'Saving...' : 'Save'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}
