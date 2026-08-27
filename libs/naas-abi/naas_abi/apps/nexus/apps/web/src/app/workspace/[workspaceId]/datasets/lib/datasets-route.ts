/**
 * The datasets URL drives the mobile list-then-detail shell.
 *
 *   /workspace/{id}/datasets                      → catalog (mobile list / desktop catalog)
 *   /workspace/{id}/datasets/{namespace}/{name}   → table detail (mobile detail)
 */

export interface DatasetsRoute {
  isDatasetsRoute: boolean;
  isTable: boolean;
  namespace: string | null;
  name: string | null;
}

const DATASETS_SEGMENT =
  /(?:^|\/)datasets(?:\/([^/?#]+))?(?:\/([^/?#]+))?(?=[/?#]|$)/;

export function parseDatasetsRoute(
  pathname: string | null | undefined,
): DatasetsRoute {
  const match = pathname ? DATASETS_SEGMENT.exec(pathname) : null;
  if (!match) {
    return { isDatasetsRoute: false, isTable: false, namespace: null, name: null };
  }
  const namespace = match[1] ?? null;
  const name = match[2] ?? null;
  return {
    isDatasetsRoute: true,
    isTable: namespace !== null && name !== null,
    namespace,
    name,
  };
}

export function datasetsCatalogPath(workspaceId: string | null): string {
  return workspaceId ? `/workspace/${workspaceId}/datasets` : '/datasets';
}

export function datasetsTablePath(
  workspaceId: string | null,
  namespace: string,
  name: string,
): string {
  return workspaceId
    ? `/workspace/${workspaceId}/datasets/${namespace}/${name}`
    : `/datasets/${namespace}/${name}`;
}
