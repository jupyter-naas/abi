'use client';

import { cn } from '@/lib/utils';
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

export type FeatureChoice = 'default' | 'on' | 'off';

const CHOICES: { id: FeatureChoice; label: string }[] = [
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

/** Features a workspace can override: the catalog without the pinned ones. */
export function configurableFeatures(catalog: WorkspaceFeatureCatalog | null): string[] {
  return catalog ? catalog.catalog.filter((key) => !catalog.pinned.includes(key)) : [];
}

export function choicesFromOverrides(
  overrides: Record<string, boolean>
): Record<string, FeatureChoice> {
  return Object.fromEntries(
    Object.entries(overrides).map(([key, on]) => [key, on ? 'on' : 'off'] as const)
  );
}

/** The overrides to save: every non-default choice on a configurable feature. */
export function overridesFromChoices(
  choices: Record<string, FeatureChoice>,
  features: string[]
): Record<string, boolean> {
  return Object.fromEntries(
    Object.entries(choices)
      .filter(([key, choice]) => choice !== 'default' && features.includes(key))
      .map(([key, choice]) => [key, choice === 'on'])
  );
}

/**
 * Per-workspace overrides of the role defaults: one row per configurable
 * feature with its role default, a Default/On/Off choice and the result.
 * Used by the Features modal and the create-workspace page.
 */
export function WorkspaceFeaturesTable({
  catalog,
  choices,
  disabled,
  onChange,
}: {
  catalog: WorkspaceFeatureCatalog;
  choices: Record<string, FeatureChoice>;
  disabled: boolean;
  onChange: (feature: string, choice: FeatureChoice) => void;
}) {
  const features = configurableFeatures(catalog);

  const defaultRoles = (feature: string): string[] =>
    catalog.roles.filter((role) => catalog.role_baseline[role]?.includes(feature));

  const resultText = (feature: string): string => {
    const choice = choices[feature] ?? 'default';
    if (choice === 'on') return 'Every role';
    if (choice === 'off') return 'Hidden';
    return rolesText(defaultRoles(feature));
  };

  return (
    <>
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
            const choice = choices[feature] ?? 'default';
            return (
              <tr key={feature} className="border-t border-border">
                <td className="py-2 pr-3 font-medium text-foreground">{featureLabel(feature)}</td>
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
                        disabled={disabled}
                        onClick={() => onChange(feature, option.id)}
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
      {catalog.pinned.length > 0 && (
        <p className="py-3 text-xs text-muted-foreground">
          {catalog.pinned.map(featureLabel).join(', ')} always follows the role defaults.
        </p>
      )}
    </>
  );
}
