'use client';

import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { useGraphRequest } from '@/hooks/use-graph-request';
import { EXPLORER_SIDEBAR_INSTANCE_LIMIT, explorerShowsGraphHint } from '@/lib/graph-explorer';
import type { ApiDiscoveryInstance } from '../individuals-table';

export function ExplorerClassInstances({
  workspaceId,
  graphs,
  classUri,
  classLabel,
  selectedUri,
  graphLabels,
  workspaceGraphCount,
  onOpen,
}: {
  workspaceId: string;
  graphs: string[];
  classUri: string;
  classLabel: string;
  selectedUri?: string | null;
  graphLabels: Record<string, string>;
  workspaceGraphCount: number;
  onOpen: (instance: { uri: string; graph_uri: string; class_uri: string }) => void;
}) {
  const request = useGraphRequest<{ items: ApiDiscoveryInstance[]; has_more: boolean }>(
    'explorer/instances',
    {
      workspace_id: workspaceId,
      graph_uris: graphs,
      class_uris: [classUri],
      search: '',
      offset: 0,
      limit: EXPLORER_SIDEBAR_INSTANCE_LIMIT,
    },
  );
  if (request.loading) {
    return (
      <p className="graph-explorer-message" role="status">
        Loading instances…
      </p>
    );
  }
  if (request.error) {
    return (
      <p className="graph-explorer-message" role="alert">
        {request.error}{' '}
        <button type="button" onClick={request.retry}>
          Retry
        </button>
      </p>
    );
  }
  const items = request.data?.items || [];
  if (!items.length) {
    return <p className="graph-explorer-message">No instances.</p>;
  }
  const showGraphHint = explorerShowsGraphHint(
    graphs,
    workspaceGraphCount,
    items.map((item) => item.graph_uri || graphs[0] || ''),
  );
  return (
    <ul>
      {items.map((item) => {
        const graphUri = item.graph_uri || graphs[0] || '';
        return (
          <li key={`${graphUri}:${item.uri}`} data-ontology-tree-row>
            <div className="graph-explorer-tree-row">
              <button
                type="button"
                data-ontology-tree-item={`${graphUri}:${item.uri}`}
                data-ontology-tree-select
                aria-current={selectedUri === item.uri ? 'page' : undefined}
                title={item.uri}
                onClick={() =>
                  onOpen({
                    uri: item.uri,
                    graph_uri: graphUri,
                    class_uri: item.class_uri || classUri,
                  })
                }
              >
                <OntologyTopicIcon subject={{ id: classUri, name: classLabel, type: 'entity' }} />
                <span>{item.label || item.uri.split(/[#/]/).pop() || item.uri}</span>
                {showGraphHint && (
                  <small className="graph-explorer-graph-hint">
                    {graphLabels[graphUri] || graphUri}
                  </small>
                )}
              </button>
            </div>
          </li>
        );
      })}
      {request.data?.has_more && (
        <li>
          <p className="graph-explorer-message">
            First {EXPLORER_SIDEBAR_INSTANCE_LIMIT} shown. Open the class to see all.
          </p>
        </li>
      )}
    </ul>
  );
}
