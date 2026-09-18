'use client';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Box, Check, Hash, Link2, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react';
import { OntologyTopicIcon } from '@/components/ontology/ontology-topic-icon';
import { classDefinitionHref, individualHref } from '@/lib/graph-instance-browser';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { ApiClassObjectProperty, RelationTargetPicker, SearchableOption, SearchablePicker } from '@/components/graph/relation-pickers';
import { useConfirm } from '@/components/ui/dialogs';
import './graph-object.css';
const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';
function propertyLabel(value: string) {
  return value.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, s => s.toUpperCase());
}
interface ApiDiscoveryInstance {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  properties: Record<string, string>;
  bfo_bucket_uri?: string;
  bfo_bucket_label?: string;
  domain_relations_count?: number;
  range_relations_count?: number;
  properties_count?: number;
}

export interface InstanceDetail {
  uri: string;
  label: string;
  class_uri: string;
  class_label: string;
  data_properties: Array<{
    predicate_uri: string;
    predicate_label: string;
    value: string;
  }>;
  relations: Array<{
    role: 'domain' | 'range';
    predicate_uri: string;
    predicate_label: string;
    other_uri: string;
    other_label: string;
  }>;
}

function compactUri(uri: string): string {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

function instanceLabel(inst: ApiDiscoveryInstance): string {
  return inst.label || inst.properties[RDFS_LABEL] || compactUri(inst.uri);
}

interface ApiDatatypeProperty {
  uri: string;
  label: string;
  kind: string;
}

interface DraftDataPropertyRow {
  id: string;
  predicateUri: string;
  value: string;
}

interface DraftRelationRow {
  id: string;
  predicateUri: string;
  targetUri: string;
}

function dataPropertyRowKey(predicateUri: string, value: string, index: number): string {
  return `dp-${predicateUri}-${value}-${index}`;
}

function objectPropertyRowKey(predicateUri: string, targetUri: string, index: number): string {
  return `op-${predicateUri}-${targetUri}-${index}`;
}

export function IndividualDetailPanel({
  instance,
  detail,
  loading,
  graphUri,
  workspaceId,
  onPropertyDeleted,
  onIndividualDeleted,
  readOnly = true,
}: {
  readOnly?: boolean;
  instance: ApiDiscoveryInstance;
  detail: InstanceDetail | null;
  loading: boolean;
  graphUri: string;
  workspaceId: string;
  onPropertyDeleted: () => void;
  onIndividualDeleted: () => void;
}) {
  const { confirm, dialog: confirmDialog } = useConfirm();
  const [deletingKeys, setDeletingKeys] = useState<Set<string>>(new Set());
  const [deletingIndividual, setDeletingIndividual] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState('');
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set());
  const [datatypeProperties, setDatatypeProperties] = useState<ApiDatatypeProperty[]>([]);
  const [datatypePropertiesLoading, setDatatypePropertiesLoading] = useState(false);
  const [draftRows, setDraftRows] = useState<DraftDataPropertyRow[]>([]);
  const [addingKeys, setAddingKeys] = useState<Set<string>>(new Set());
  const [newPredicateUri, setNewPredicateUri] = useState('');
  const [newPropertyValue, setNewPropertyValue] = useState('');
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [schemaObjectProperties, setSchemaObjectProperties] = useState<ApiClassObjectProperty[]>([]);
  const [schemaObjectPropertiesLoading, setSchemaObjectPropertiesLoading] = useState(false);
  const [editingRelationKey, setEditingRelationKey] = useState<string | null>(null);
  const [editingPredicateUri, setEditingPredicateUri] = useState('');
  const [editingTargetUri, setEditingTargetUri] = useState('');
  const [relationDraftRows, setRelationDraftRows] = useState<DraftRelationRow[]>([]);
  const [addingRelationKeys, setAddingRelationKeys] = useState<Set<string>>(new Set());
  const [newRelationPredicateUri, setNewRelationPredicateUri] = useState('');
  const [newRelationTargetUri, setNewRelationTargetUri] = useState('');
  const [isAddingRelation, setIsAddingRelation] = useState(false);
  const [relationAddError, setRelationAddError] = useState<string | null>(null);

  const [mutationError, setMutationError] = useState<string | null>(null);
  const mutate = async (url: string, options: RequestInit) => {
    if (readOnly) throw new Error('This graph is read-only.');
    setMutationError(null);
    const response = await authFetch(url, options);
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'The change could not be saved. Please try again.');
    }
    return response;
  };

  const classUri = detail?.class_uri || instance.class_uri;
  const dataProperties = detail?.data_properties ?? [];
  const canAddProperties = datatypeProperties.length > 0 && !datatypePropertiesLoading;

  useEffect(() => {
    if (readOnly || !classUri) {
      setDatatypeProperties([]);
      return;
    }
    let cancelled = false;
    setDatatypePropertiesLoading(true);
    const classParams = new URLSearchParams({
      workspace_id: workspaceId,
      class_uri: classUri,
    });
    void Promise.all([
      authFetch(
        `${getApiUrl()}/api/graph/discovery/class-datatype-properties?${classParams.toString()}`
      ),
      authFetch(`${getApiUrl()}/api/graph/discovery/properties`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          class_uris: [classUri],
        }),
      }),
    ])
      .then(async ([schemaRes, graphRes]) => {
        const schemaProps = schemaRes.ok
          ? ((await schemaRes.json()) as ApiDatatypeProperty[])
          : [];
        const graphProps = graphRes.ok ? ((await graphRes.json()) as ApiDatatypeProperty[]) : [];
        const merged = new Map<string, ApiDatatypeProperty>();
        for (const prop of [...schemaProps, ...graphProps]) {
          if (prop?.uri) merged.set(prop.uri, prop);
        }
        return [...merged.values()].sort((a, b) =>
          (a.label || a.uri).localeCompare(b.label || b.uri, undefined, { sensitivity: 'base' })
        );
      })
      .then((merged) => {
        if (!cancelled) setDatatypeProperties(merged);
      })
      .catch(() => {
        if (!cancelled) setDatatypeProperties([]);
      })
      .finally(() => {
        if (!cancelled) setDatatypePropertiesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, classUri, graphUri, readOnly]);

  useEffect(() => {
    if (datatypeProperties.length > 0 && !newPredicateUri) {
      setNewPredicateUri(datatypeProperties[0].uri);
    }
  }, [datatypeProperties, newPredicateUri]);

  useEffect(() => {
    if (readOnly || !classUri) {
      setSchemaObjectProperties([]);
      return;
    }
    let cancelled = false;
    setSchemaObjectPropertiesLoading(true);
    const params = new URLSearchParams({
      workspace_id: workspaceId,
      class_uri: classUri,
    });
    void authFetch(
      `${getApiUrl()}/api/graph/discovery/class-object-properties?${params.toString()}`
    )
      .then(async (res) => {
        if (cancelled) return;
        if (res.ok) {
          const data = (await res.json()) as ApiClassObjectProperty[];
          setSchemaObjectProperties(Array.isArray(data) ? data : []);
        } else {
          setSchemaObjectProperties([]);
        }
      })
      .catch(() => {
        if (!cancelled) setSchemaObjectProperties([]);
      })
      .finally(() => {
        if (!cancelled) setSchemaObjectPropertiesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, classUri, readOnly]);

  useEffect(() => {
    if (schemaObjectProperties.length > 0 && !newRelationPredicateUri) {
      setNewRelationPredicateUri(schemaObjectProperties[0].uri);
    }
  }, [schemaObjectProperties, newRelationPredicateUri]);

  useEffect(() => {
    setDraftRows([]);
    setEditingKey(null);
    setEditingValue('');
    setNewPredicateUri('');
    setNewPropertyValue('');
    setAddError(null);
    setRelationDraftRows([]);
    setEditingRelationKey(null);
    setEditingPredicateUri('');
    setEditingTargetUri('');
    setNewRelationPredicateUri('');
    setNewRelationTargetUri('');
    setRelationAddError(null);
  }, [instance.uri, readOnly]);

  const objectProperties = useMemo(
    () =>
      (detail?.relations ?? [])
        .filter((r) => r.role === 'domain')
        .map((r) => ({
          predicate_uri: r.predicate_uri,
          predicate: r.predicate_label,
          targetId: r.other_uri,
          targetLabel: r.other_label || compactUri(r.other_uri),
        })),
    [detail]
  );

  const relationPropertyOptions = useMemo(() => {
    const merged = new Map<string, ApiClassObjectProperty>();
    for (const prop of schemaObjectProperties) {
      merged.set(prop.uri, prop);
    }
    for (const op of objectProperties) {
      if (!merged.has(op.predicate_uri)) {
        merged.set(op.predicate_uri, {
          uri: op.predicate_uri,
          label: op.predicate,
          range_options: [],
        });
      }
    }
    return [...merged.values()].sort((a, b) =>
      (a.label || a.uri).localeCompare(b.label || b.uri, undefined, { sensitivity: 'base' })
    );
  }, [schemaObjectProperties, objectProperties]);

  const relationPropertyPickerOptions: SearchableOption[] = useMemo(
    () =>
      relationPropertyOptions.map((prop) => ({
        uri: prop.uri,
        label: prop.label,
      })),
    [relationPropertyOptions]
  );

  const canAddRelations =
    relationPropertyOptions.length > 0 && !schemaObjectPropertiesLoading;

  const findRelationProperty = (predicateUri: string) =>
    relationPropertyOptions.find((prop) => prop.uri === predicateUri);

  const handleDeleteDataProperty = async (predicateUri: string, value: string, key: string) => {
    const ok = await confirm({
      title: 'Delete data property?',
      description: `Remove "${compactUri(predicateUri)}" = "${value}" from this individual.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setDeletingKeys((prev) => new Set(prev).add(key));
    try {
      await mutate(`${getApiUrl()}/api/graph/nodes/data-property/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
          predicate_uri: predicateUri,
          value,
        }),
      });
      onPropertyDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      setDeletingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleSaveDataProperty = async (
    predicateUri: string,
    oldValue: string,
    newValue: string,
    key: string
  ) => {
    const trimmed = newValue.trim();
    if (!trimmed || trimmed === oldValue) {
      setEditingKey(null);
      setEditingValue('');
      return;
    }
    setSavingKeys((prev) => new Set(prev).add(key));
    try {
      await mutate(`${getApiUrl()}/api/graph/nodes/data-property/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
          predicate_uri: predicateUri,
          old_value: oldValue,
          new_value: trimmed,
        }),
      });
      setEditingKey(null);
      setEditingValue('');
      onPropertyDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      setSavingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleSaveObjectProperty = async (
    oldPredicateUri: string,
    oldTargetUri: string,
    newPredicateUri: string,
    newTargetUri: string,
    key: string
  ) => {
    if (
      !newPredicateUri ||
      !newTargetUri ||
      (newPredicateUri === oldPredicateUri && newTargetUri === oldTargetUri)
    ) {
      setEditingRelationKey(null);
      setEditingPredicateUri('');
      setEditingTargetUri('');
      return;
    }
    setSavingKeys((prev) => new Set(prev).add(key));
    try {
      await mutate(`${getApiUrl()}/api/graph/nodes/object-property/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
          old_predicate_uri: oldPredicateUri,
          old_other_uri: oldTargetUri,
          new_predicate_uri: newPredicateUri,
          new_other_uri: newTargetUri,
        }),
      });
      setEditingRelationKey(null);
      setEditingPredicateUri('');
      setEditingTargetUri('');
      onPropertyDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      setSavingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleAddObjectProperty = async (
    predicateUri: string,
    targetUri: string,
    key: string,
    options?: { clearMainForm?: boolean }
  ) => {
    if (!predicateUri || !targetUri) return;
    const isMainForm = key === 'main-relation-form';
    if (isMainForm) {
      setIsAddingRelation(true);
      setRelationAddError(null);
    } else {
      setAddingRelationKeys((prev) => new Set(prev).add(key));
    }
    try {
      const res = await mutate(`${getApiUrl()}/api/graph/nodes/object-property/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
          predicate_uri: predicateUri,
          other_uri: targetUri,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        const message =
          typeof payload?.detail === 'string'
            ? payload.detail
            : `Failed to add relation (${res.status})`;
        if (isMainForm) setRelationAddError(message);
        return;
      }
      if (isMainForm || options?.clearMainForm) {
        setNewRelationTargetUri('');
        setRelationAddError(null);
      }
      if (!isMainForm) {
        setRelationDraftRows((prev) => prev.filter((row) => row.id !== key));
      }
      onPropertyDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      if (isMainForm) {
        setIsAddingRelation(false);
      } else {
        setAddingRelationKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    }
  };

  const addRelationDraftRow = () => {
    const defaultPredicate = relationPropertyOptions[0]?.uri ?? '';
    setRelationDraftRows((prev) => [
      ...prev,
      { id: `rel-draft-${Date.now()}-${prev.length}`, predicateUri: defaultPredicate, targetUri: '' },
    ]);
  };

  const removeRelationDraftRow = (id: string) => {
    setRelationDraftRows((prev) => prev.filter((row) => row.id !== id));
  };

  const updateRelationDraftRow = (
    id: string,
    updates: Partial<Pick<DraftRelationRow, 'predicateUri' | 'targetUri'>>
  ) => {
    setRelationDraftRows((prev) =>
      prev.map((row) => {
        if (row.id !== id) return row;
        const next = { ...row, ...updates };
        if (updates.predicateUri && updates.predicateUri !== row.predicateUri) {
          next.targetUri = '';
        }
        return next;
      })
    );
  };

  const handleDeleteObjectProperty = async (
    predicateUri: string,
    predicate: string,
    targetId: string,
    targetLabel: string,
    key: string
  ) => {
    const ok = await confirm({
      title: 'Delete object property?',
      description: `Remove "${predicate}" → "${targetLabel}" from this individual.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setDeletingKeys((prev) => new Set(prev).add(key));
    try {
      await mutate(`${getApiUrl()}/api/graph/nodes/object-property/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
          predicate_uri: predicateUri,
          other_uri: targetId,
        }),
      });
      onPropertyDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      setDeletingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const addDraftRow = () => {
    const defaultPredicate = datatypeProperties[0]?.uri ?? '';
    setDraftRows((prev) => [
      ...prev,
      { id: `draft-${Date.now()}-${prev.length}`, predicateUri: defaultPredicate, value: '' },
    ]);
  };

  const removeDraftRow = (id: string) => {
    setDraftRows((prev) => prev.filter((row) => row.id !== id));
  };

  const updateDraftRow = (id: string, updates: Partial<Pick<DraftDataPropertyRow, 'predicateUri' | 'value'>>) => {
    setDraftRows((prev) =>
      prev.map((row) => (row.id === id ? { ...row, ...updates } : row))
    );
  };

  const handleAddDataProperty = async (
    predicateUri: string,
    value: string,
    key: string,
    options?: { clearMainForm?: boolean }
  ) => {
    const trimmed = value.trim();
    if (!predicateUri || !trimmed) return;
    const isMainForm = key === 'main-add-form';
    if (isMainForm) {
      setIsAddingNew(true);
      setAddError(null);
    } else {
      setAddingKeys((prev) => new Set(prev).add(key));
    }
    try {
      const res = await mutate(`${getApiUrl()}/api/graph/nodes/data-property/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
          predicate_uri: predicateUri,
          value: trimmed,
        }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        const message =
          typeof payload?.detail === 'string'
            ? payload.detail
            : `Failed to add property (${res.status})`;
        if (isMainForm) setAddError(message);
        return;
      }
      if (isMainForm || options?.clearMainForm) {
        setNewPropertyValue('');
        setAddError(null);
      }
      if (!isMainForm) {
        setDraftRows((prev) => prev.filter((row) => row.id !== key));
      }
      onPropertyDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      if (isMainForm) {
        setIsAddingNew(false);
      } else {
        setAddingKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      }
    }
  };

  const handleDeleteIndividual = async () => {
    const ok = await confirm({
      title: 'Delete individual?',
      description: `This will permanently remove "${instanceLabel(instance)}" and all its triples from the graph.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    setDeletingIndividual(true);
    try {
      await mutate(`${getApiUrl()}/api/graph/nodes/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
        }),
      });
      onIndividualDeleted();
    } catch (error) {
      setMutationError(error instanceof Error ? error.message : 'The change could not be saved. Please try again.');
    } finally {
      setDeletingIndividual(false);
    }
  };

  return (
    <article className="graph-object-editor">
      {confirmDialog}
      {mutationError && <p role="alert" className="graph-object-error">{mutationError}</p>}

      <header className="graph-object-heading">
        <div className="graph-object-title">
          <OntologyTopicIcon subject={{ id: instance.class_uri, name: instance.class_label, type: 'entity' }} />
          <div className="min-w-0 flex-1">
            <h1>{instanceLabel(instance)}</h1>

          </div>
          {!readOnly && <button
            type="button"
            disabled={deletingIndividual}
            onClick={() => void handleDeleteIndividual()}
            className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs text-red-500 transition-colors hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-900/20"
          >
            {deletingIndividual ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Trash2 size={12} />
            )}
            Remove
          </button>}
        </div>
        <div className="ml-13 flex items-center gap-2">
          <Box size={14} className="text-blue-500" />
          {instance.class_uri && <Link href={classDefinitionHref(workspaceId, instance.class_uri)} className="text-sm text-workspace-accent hover:underline">
            {instance.class_label || compactUri(instance.class_uri)}
          </Link>}
        </div>
        <details className="graph-object-identifier"><summary>Identifier</summary><code>{instance.uri}</code></details>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading properties…
        </div>
      ) : (
        <>
          <div className="mb-6">
            <h3 className="mb-3 flex items-center gap-2 font-medium">
              <Hash size={16} className="text-purple-500" />
              Properties
              <span className="text-xs text-muted-foreground">({dataProperties.length})</span>
            </h3>

            {dataProperties.length === 0 ? (
              <p className="mb-3 rounded-lg border p-4 text-center text-sm text-muted-foreground">
                No properties yet.
              </p>
            ) : (
              <div className="graph-object-rows">
                {dataProperties.map((dp, i) => {
                  const rowKey = dataPropertyRowKey(dp.predicate_uri, dp.value, i);
                  const isDeleting = deletingKeys.has(rowKey);
                  const isSaving = savingKeys.has(rowKey);
                  const isEditing = editingKey === rowKey;
                  return (
                    <div
                      key={rowKey}
                      className="graph-object-property"
                    >
                      <div className="graph-object-property-name" title={dp.predicate_uri}>
                        {propertyLabel(dp.predicate_label)}
                      </div>
                      <div className="min-w-0 flex-1">
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <input
                              autoFocus
                              value={editingValue}
                              onChange={(e) => setEditingValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter')
                                  void handleSaveDataProperty(
                                    dp.predicate_uri,
                                    dp.value,
                                    editingValue,
                                    rowKey
                                  );
                                if (e.key === 'Escape') {
                                  setEditingKey(null);
                                  setEditingValue('');
                                }
                              }}
                              className="flex-1 rounded border bg-background px-2 py-0.5 text-sm outline-none focus:ring-1 focus:ring-primary"
                            />
                            <button
                              type="button"
                              disabled={isSaving}
                              onClick={() =>
                                void handleSaveDataProperty(
                                  dp.predicate_uri,
                                  dp.value,
                                  editingValue,
                                  rowKey
                                )
                              }
                              title="Save"
                              className="flex h-6 w-6 items-center justify-center rounded text-green-600 transition-colors hover:bg-green-50 disabled:opacity-50 dark:hover:bg-green-900/20"
                            >
                              {isSaving ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <Check size={12} />
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingKey(null);
                                setEditingValue('');
                              }}
                              title="Cancel"
                              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        ) : (
                          <span className="break-all text-muted-foreground">{dp.value}</span>
                        )}
                      </div>
                      {!readOnly && !isEditing && (
                        <div className="flex shrink-0 items-center gap-1">
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() => {
                              setEditingKey(rowKey);
                              setEditingValue(dp.value);
                            }}
                            title="Edit property"
                            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                          >
                            <Pencil size={12} />
                          </button>
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() =>
                              void handleDeleteDataProperty(
                                dp.predicate_uri,
                                dp.value,
                                rowKey
                              )
                            }
                            title="Remove this value"
                            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20"
                          >
                            {isDeleting ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (
                              <Trash2 size={12} />
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {draftRows.length > 0 && (
              <div className="graph-object-rows">
                {draftRows.map((draft) => {
                  const isAdding = addingKeys.has(draft.id);
                  const selectedProperty = datatypeProperties.find(
                    (p) => p.uri === draft.predicateUri
                  );
                  return (
                    <div
                      key={draft.id}
                      className="flex items-start gap-3 rounded-lg border border-dashed bg-muted/20 px-4 py-2.5 text-sm"
                    >
                      <div className="w-2/5 shrink-0">
                        <select
                          value={draft.predicateUri}
                          onChange={(e) =>
                            updateDraftRow(draft.id, { predicateUri: e.target.value })
                          }
                          className="w-full rounded border bg-background px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-primary"
                        >
                          {datatypeProperties.map((prop) => (
                            <option key={prop.uri} value={prop.uri}>
                              {prop.label}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="min-w-0 flex-1">
                        <input
                          value={draft.value}
                          onChange={(e) => updateDraftRow(draft.id, { value: e.target.value })}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter')
                              void handleAddDataProperty(
                                draft.predicateUri,
                                draft.value,
                                draft.id
                              );
                          }}
                          placeholder={
                            selectedProperty
                              ? `Value for ${selectedProperty.label}`
                              : 'Property value'
                          }
                          className="w-full rounded border bg-background px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-primary"
                        />
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          disabled={isAdding || !draft.predicateUri || !draft.value.trim()}
                          onClick={() =>
                            void handleAddDataProperty(
                              draft.predicateUri,
                              draft.value,
                              draft.id
                            )
                          }
                          title="Save property"
                          className="flex h-6 w-6 items-center justify-center rounded text-green-600 transition-colors hover:bg-green-50 disabled:opacity-50 dark:hover:bg-green-900/20"
                        >
                          {isAdding ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Check size={12} />
                          )}
                        </button>
                        <button
                          type="button"
                          disabled={isAdding}
                          onClick={() => removeDraftRow(draft.id)}
                          title="Remove row"
                          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {!readOnly && <details className="graph-object-add">
              <summary>Add property</summary>
              <div className="mb-3 flex items-center justify-between gap-2">
                <span>New property</span>
                {canAddProperties && (
                  <button
                    type="button"
                    onClick={addDraftRow}
                    className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Plus size={12} />
                    Another row
                  </button>
                )}
              </div>

              {datatypePropertiesLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 size={14} className="animate-spin" />
                  Loading available properties…
                </div>
              ) : !canAddProperties ? (
                <p className="text-sm text-muted-foreground">
                  {classUri
                    ? 'No datatype properties found for this class.'
                    : 'Assign a class to this individual to add data properties.'}
                </p>
              ) : (
                <>
                  <div className="flex items-start gap-3 text-sm">
                    <div className="w-2/5 shrink-0">
                      <select
                        value={newPredicateUri}
                        onChange={(e) => setNewPredicateUri(e.target.value)}
                        className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
                      >
                        {datatypeProperties.map((prop) => (
                          <option key={prop.uri} value={prop.uri}>
                            {prop.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="min-w-0 flex-1">
                      <input
                        value={newPropertyValue}
                        onChange={(e) => {
                          setNewPropertyValue(e.target.value);
                          if (addError) setAddError(null);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter')
                            void handleAddDataProperty(
                              newPredicateUri,
                              newPropertyValue,
                              'main-add-form'
                            );
                        }}
                        placeholder="Enter value"
                        className="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-primary"
                      />
                    </div>
                    <button
                      type="button"
                      disabled={
                        isAddingNew || !newPredicateUri || !newPropertyValue.trim()
                      }
                      onClick={() =>
                        void handleAddDataProperty(
                          newPredicateUri,
                          newPropertyValue,
                          'main-add-form'
                        )
                      }
                      className="flex shrink-0 items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isAddingNew ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Plus size={12} />
                      )}
                      Add
                    </button>
                  </div>
                  {addError && (
                    <p className="mt-2 text-xs text-destructive">{addError}</p>
                  )}
                </>
              )}
            </details>}
          </div>

          <div>
            <h3 className="mb-3 flex items-center gap-2 font-medium">
              <Link2 size={16} className="text-green-500" />
              Connections
              <span className="text-xs text-muted-foreground">({objectProperties.length})</span>
            </h3>

            {objectProperties.length === 0 ? (
              <p className="mb-3 rounded-lg border p-4 text-center text-sm text-muted-foreground">
                No connections yet.
              </p>
            ) : (
              <div className="graph-object-rows">
                {objectProperties.map((op, i) => {
                  const rowKey = objectPropertyRowKey(op.predicate_uri, op.targetId, i);
                  const isDeleting = deletingKeys.has(rowKey);
                  const isSaving = savingKeys.has(rowKey);
                  const isEditing = editingRelationKey === rowKey;
                  const editingProperty = findRelationProperty(editingPredicateUri);
                  return (
                    <div
                      key={rowKey}
                      className="graph-object-relation"
                    >
                      {isEditing ? (
                        <div className="flex flex-wrap items-center gap-2">
                          <SearchablePicker
                            value={editingPredicateUri}
                            options={relationPropertyPickerOptions}
                            placeholder="Search relation..."
                            searchPlaceholder="Search relation label..."
                            emptyMessage="No matching relations"
                            onChange={(predicateUri) => {
                              setEditingPredicateUri(predicateUri);
                              if (predicateUri !== op.predicate_uri) {
                                setEditingTargetUri('');
                              }
                            }}
                          />
                          <span className="text-xs text-muted-foreground">→</span>
                          <RelationTargetPicker
                            predicateUri={editingPredicateUri}
                            property={editingProperty}
                            value={editingTargetUri}
                            graphUri={graphUri}
                            workspaceId={workspaceId}
                            onChange={setEditingTargetUri}
                          />
                          <div className="flex shrink-0 items-center gap-1">
                            <button
                              type="button"
                              disabled={isSaving || !editingPredicateUri || !editingTargetUri}
                              onClick={() =>
                                void handleSaveObjectProperty(
                                  op.predicate_uri,
                                  op.targetId,
                                  editingPredicateUri,
                                  editingTargetUri,
                                  rowKey
                                )
                              }
                              title="Save relation"
                              className="flex h-6 w-6 items-center justify-center rounded text-green-600 transition-colors hover:bg-green-50 disabled:opacity-50 dark:hover:bg-green-900/20"
                            >
                              {isSaving ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <Check size={12} />
                              )}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingRelationKey(null);
                                setEditingPredicateUri('');
                                setEditingTargetUri('');
                              }}
                              title="Cancel"
                              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start gap-3">
                          <div className="graph-object-property-name" title={op.predicate_uri}>
                            {propertyLabel(op.predicate)}
                          </div>
                          <div className="min-w-0 flex-1">
                            <Link className="graph-object-link" href={individualHref(workspaceId, graphUri, '', op.targetId)}>{op.targetLabel}</Link>
                            {op.targetLabel !== op.targetId && (
                              <span
                                className="mt-0.5 block truncate font-mono text-xs text-muted-foreground"
                                title={op.targetId}
                              >
                                {op.targetId}
                              </span>
                            )}
                          </div>
                          {!readOnly && <div className="flex shrink-0 items-center gap-1">
                            <button
                              type="button"
                              disabled={isDeleting}
                              onClick={() => {
                                setEditingRelationKey(rowKey);
                                setEditingPredicateUri(op.predicate_uri);
                                setEditingTargetUri(op.targetId);
                              }}
                              title="Edit relation"
                              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-40"
                            >
                              <Pencil size={12} />
                            </button>
                            <button
                              type="button"
                              disabled={isDeleting}
                              onClick={() =>
                                void handleDeleteObjectProperty(
                                  op.predicate_uri,
                                  op.predicate,
                                  op.targetId,
                                  op.targetLabel,
                                  rowKey
                                )
                              }
                              title="Remove relation"
                              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20"
                            >
                              {isDeleting ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <Trash2 size={12} />
                              )}
                            </button>
                          </div>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {relationDraftRows.length > 0 && (
              <div className="graph-object-rows">
                {relationDraftRows.map((draft) => {
                  const isAdding = addingRelationKeys.has(draft.id);
                  const draftProperty = findRelationProperty(draft.predicateUri);
                  return (
                    <div
                      key={draft.id}
                      className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed bg-muted/20 px-4 py-2.5 text-sm"
                    >
                      <SearchablePicker
                        value={draft.predicateUri}
                        options={relationPropertyPickerOptions}
                        placeholder="Search relation..."
                        searchPlaceholder="Search relation label..."
                        emptyMessage="No matching relations"
                        onChange={(predicateUri) =>
                          updateRelationDraftRow(draft.id, { predicateUri })
                        }
                      />
                      <span className="text-xs text-muted-foreground">→</span>
                      <RelationTargetPicker
                        predicateUri={draft.predicateUri}
                        property={draftProperty}
                        value={draft.targetUri}
                        graphUri={graphUri}
                        workspaceId={workspaceId}
                        onChange={(targetUri) =>
                          updateRelationDraftRow(draft.id, { targetUri })
                        }
                      />
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          disabled={isAdding || !draft.predicateUri || !draft.targetUri}
                          onClick={() =>
                            void handleAddObjectProperty(
                              draft.predicateUri,
                              draft.targetUri,
                              draft.id
                            )
                          }
                          title="Save relation"
                          className="flex h-6 w-6 items-center justify-center rounded text-green-600 transition-colors hover:bg-green-50 disabled:opacity-50 dark:hover:bg-green-900/20"
                        >
                          {isAdding ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Check size={12} />
                          )}
                        </button>
                        <button
                          type="button"
                          disabled={isAdding}
                          onClick={() => removeRelationDraftRow(draft.id)}
                          title="Remove row"
                          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/20"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {!readOnly && <details className="graph-object-add">
              <summary>Add connection</summary>
              <div className="mb-3 flex items-center justify-between gap-2">
                <span>New connection</span>
                {canAddRelations && (
                  <button
                    type="button"
                    onClick={addRelationDraftRow}
                    className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Plus size={12} />
                    Another row
                  </button>
                )}
              </div>

              {schemaObjectPropertiesLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 size={14} className="animate-spin" />
                  Loading available relations…
                </div>
              ) : !canAddRelations ? (
                <p className="text-sm text-muted-foreground">
                  {classUri
                    ? 'No object properties found for this class.'
                    : 'Assign a class to this individual to add relations.'}
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <SearchablePicker
                      value={newRelationPredicateUri}
                      options={relationPropertyPickerOptions}
                      placeholder="Search relation..."
                      searchPlaceholder="Search relation label..."
                      emptyMessage="No matching relations"
                      onChange={(predicateUri) => {
                        setNewRelationPredicateUri(predicateUri);
                        setNewRelationTargetUri('');
                        if (relationAddError) setRelationAddError(null);
                      }}
                    />
                    <span className="text-xs text-muted-foreground">→</span>
                    <RelationTargetPicker
                      predicateUri={newRelationPredicateUri}
                      property={findRelationProperty(newRelationPredicateUri)}
                      value={newRelationTargetUri}
                      graphUri={graphUri}
                      workspaceId={workspaceId}
                      onChange={(targetUri) => {
                        setNewRelationTargetUri(targetUri);
                        if (relationAddError) setRelationAddError(null);
                      }}
                    />
                    <button
                      type="button"
                      disabled={
                        isAddingRelation || !newRelationPredicateUri || !newRelationTargetUri
                      }
                      onClick={() =>
                        void handleAddObjectProperty(
                          newRelationPredicateUri,
                          newRelationTargetUri,
                          'main-relation-form'
                        )
                      }
                      className="flex shrink-0 items-center gap-1.5 rounded-md bg-workspace-accent px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isAddingRelation ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Plus size={12} />
                      )}
                      Add
                    </button>
                  </div>
                  {relationAddError && (
                    <p className="mt-2 text-xs text-destructive">{relationAddError}</p>
                  )}
                </>
              )}
            </details>}
          </div>
        </>
      )}
    </article>
  );
}
