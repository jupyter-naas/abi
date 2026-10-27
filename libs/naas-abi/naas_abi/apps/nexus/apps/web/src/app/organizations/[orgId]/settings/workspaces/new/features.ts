/**
 * The features of a new workspace: its feature set, picked among what its organization offers.
 * No React here.
 */

/** `GET /api/organizations/{org}/workspace-features`, the parts the create form reads. */
export interface WorkspaceFeatureCatalog {
  /** The deployment's enabled features. */
  catalog: string[];
  /** The organization's effective features: what a workspace of it may have. */
  available?: string[];
}

/** The features to offer: the organization's, else the deployment's. */
export function featureChoices(catalog: WorkspaceFeatureCatalog | null): string[] {
  if (!catalog) return [];
  return catalog.available ?? catalog.catalog;
}

/**
 * The `features` to send: `null` (nothing recorded: everything the organization has) when every
 * choice is on, else the checked ones in the order offered.
 */
export function featuresPayload(checked: ReadonlySet<string>, choices: string[]): string[] | null {
  if (choices.every((feature) => checked.has(feature))) return null;
  return choices.filter((feature) => checked.has(feature));
}

/** Whether the new workspace will have a feature (all of them until the catalog is known). */
export function featureOn(feature: string, checked: ReadonlySet<string> | null): boolean {
  return checked === null || checked.has(feature);
}
