'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, X } from 'lucide-react';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { useGraphRequest } from '@/hooks/use-graph-request';
import { useOntologyIconsStore } from '@/stores/ontology-icons';
import { classDefinitionHref, individualHref } from '@/lib/graph-instance-browser';
import './instance-browser.css';

export interface DiscoveryInstance {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
}

interface InstanceDetail extends DiscoveryInstance {
  data_properties: Array<{ predicate_uri: string; predicate_label: string; value: string }>;
  relations: Array<{ role: 'domain' | 'range'; predicate_uri: string; predicate_label: string; other_uri: string; other_label: string }>;
}

function compactUri(uri: string): string {
  return uri.split(/[#/]/).filter(Boolean).pop() || uri;
}

export function InstanceInspector({ instance, graphUri, graphLabel, workspaceId, onClose, onSelectInstance }: {
  instance: DiscoveryInstance;
  graphUri: string;
  graphLabel?: string;
  workspaceId: string;
  onClose: () => void;
  onSelectInstance?: (instance: DiscoveryInstance) => void;
}) {
  const [roleFilter, setRoleFilter] = useState<'domain' | 'range'>('domain');
  const loadIcons = useOntologyIconsStore(state => state.load);
  useEffect(() => { void loadIcons(workspaceId); }, [workspaceId, loadIcons]);
  const { data: detail, loading, error, retry } = useGraphRequest<InstanceDetail>('discovery/instance-detail', {
    workspace_id: workspaceId, graph_uri: graphUri, instance_uri: instance.uri,
  });
  const label = detail?.label || instance.label || compactUri(instance.uri);
  const classUri = detail?.class_uri || instance.class_uri;
  const classLabel = detail?.class_label || instance.class_label || compactUri(classUri);
  const relations = (detail?.relations ?? []).filter(relation => relation.role === roleFilter);

  return <section className="graph-instance-inspector" aria-label="Instance details">
    <header className="graph-browser-heading">
      <div><OntologyTopicIcon subject={{ id: classUri, name: classLabel || label, type: 'entity' }} /><h2>{label}</h2>
        {classUri && <Link className="graph-browser-class-link" href={classDefinitionHref(workspaceId, classUri)}>{classLabel}<ArrowUpRight size={13} /></Link>}
      </div>
      <button className="graph-browser-icon-button" type="button" aria-label="Close inspector" onClick={onClose}><X size={16} /></button>
    </header>
    <div className="graph-inspector-content">
      <p className="graph-browser-scope" title={graphUri}>Graph · {graphLabel || compactUri(graphUri)}</p>
      {loading ? <p className="graph-browser-message" role="status">Loading details…</p> : error ? <p className="graph-browser-message" role="alert">{error} <button type="button" onClick={retry}>Retry</button></p> : detail && <>
        <section className="graph-inspector-section"><h3>Properties <small>{detail.data_properties.length}</small></h3>
          {detail.data_properties.length ? <dl className="graph-inspector-properties">{detail.data_properties.map((property, index) => <div key={`${property.predicate_uri}:${index}`}><dt title={property.predicate_uri}>{property.predicate_label || compactUri(property.predicate_uri)}</dt><dd>{property.value}</dd></div>)}</dl> : <p className="graph-browser-muted">No properties recorded.</p>}
        </section>
        <section className="graph-inspector-section"><h3>Relationships <small>{detail.relations.length}</small></h3>
          <div className="graph-inspector-directions" aria-label="Relationship direction">{(['domain', 'range'] as const).map(role => <button type="button" key={role} aria-pressed={roleFilter === role} onClick={() => setRoleFilter(role)}>{role === 'domain' ? 'Outgoing' : 'Incoming'} <span>{detail.relations.filter(relation => relation.role === role).length}</span></button>)}</div>
          {relations.length ? <ul className="graph-inspector-relations">{relations.map((relation, index) => <li key={`${relation.predicate_uri}:${relation.other_uri}:${index}`}>
            <span title={relation.predicate_uri}>{relation.predicate_label || compactUri(relation.predicate_uri)}</span>
            {onSelectInstance ? <button type="button" title={relation.other_uri} onClick={() => onSelectInstance({ uri: relation.other_uri, label: relation.other_label, class_uri: '', class_label: '' })}>{relation.other_label || compactUri(relation.other_uri)}<ArrowUpRight size={13} /></button> : <Link title={relation.other_uri} href={individualHref(workspaceId, graphUri, '', relation.other_uri)}>{relation.other_label || compactUri(relation.other_uri)}<ArrowUpRight size={13} /></Link>}
          </li>)}</ul> : <p className="graph-browser-muted">No {roleFilter === 'domain' ? 'outgoing' : 'incoming'} relationships recorded.</p>}
        </section>
      </>}
      <details className="graph-inspector-identifiers"><summary>Identifiers</summary><dl><dt>Instance</dt><dd>{instance.uri}</dd>{classUri && <><dt>Class</dt><dd>{classUri}</dd></>}<dt>Graph</dt><dd>{graphUri}</dd></dl></details>
    </div>
    <footer className="graph-inspector-footer"><Link href={individualHref(workspaceId, graphUri, classUri, instance.uri)}>Open full page <ArrowUpRight size={14} /></Link></footer>
  </section>;
}
