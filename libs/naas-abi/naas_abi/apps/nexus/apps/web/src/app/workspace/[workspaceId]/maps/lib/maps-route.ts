/**
 * The maps URL drives the mobile list-then-detail shell.
 *
 *   /workspace/{id}/maps              → dataset library (mobile list / desktop library)
 *   /workspace/{id}/maps/{datasetId}  → loaded dataset canvas (mobile detail)
 */

export interface MapsRoute {
  /** On a maps route at all. */
  isMapsRoute: boolean;
  /** A dataset canvas is open (mobile detail). */
  isDataset: boolean;
  /** Dataset id from the URL, when present. */
  datasetId: string | null;
}

// Lookahead, not a consumed terminator: same contract as parseFilesRoute.
const MAPS_SEGMENT = /(?:^|\/)maps(?:\/([^/?#]+))?(?=[/?#]|$)/;

export function parseMapsRoute(pathname: string | null | undefined): MapsRoute {
  const match = pathname ? MAPS_SEGMENT.exec(pathname) : null;
  if (!match) {
    return { isMapsRoute: false, isDataset: false, datasetId: null };
  }
  const datasetId = match[1] ?? null;
  return {
    isMapsRoute: true,
    isDataset: datasetId !== null,
    datasetId,
  };
}

/** Path of a dataset canvas for a workspace (mobile detail). */
export function mapsDatasetPath(
  workspaceId: string | null,
  datasetId: string,
): string {
  return workspaceId
    ? `/workspace/${workspaceId}/maps/${datasetId}`
    : `/maps/${datasetId}`;
}

/** Path of the maps library for a workspace. */
export function mapsLibraryPath(workspaceId: string | null): string {
  return workspaceId ? `/workspace/${workspaceId}/maps` : '/maps';
}
