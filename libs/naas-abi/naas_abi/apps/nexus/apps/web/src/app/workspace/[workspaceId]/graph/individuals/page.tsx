'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  Box,
  Check,
  ChevronRight,
  Circle,
  Hash,
  Link2,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import { BFO_BUCKET_DEFS } from '@/lib/bfo-buckets';
import { CheckboxFilter } from '@/components/graph/checkbox-filter';
import { GraphDevBanner } from '@/components/graph/graph-dev-banner';
import {
  ApiClassObjectProperty,
  RelationTargetPicker,
  SearchableOption,
  SearchablePicker,
} from '@/components/graph/relation-pickers';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { useConfirm } from '@/components/ui/dialogs';

const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label';

interface ApiGraphInfo {
  id: string;
  uri: string;
  label: string;
  role_label: string;
}

interface ApiGraphPack {
  role_label: string;
  graphs: ApiGraphInfo[];
}

interface ApiDiscoveryClass {
  uri: string;
  label: string;
  count: number;
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

interface InstanceDetail {
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

function isSystemGraph(graph: { id: string; label?: string }): boolean {
  const id = graph.id.trim().toLowerCase();
  const name = (graph.label ?? '').trim().toLowerCase();
  return (
    id === 'schema' ||
    id === 'nexus' ||
    id.endsWith('/schema') ||
    id.endsWith('/nexus') ||
    name === 'schema' ||
    name === 'nexus'
  );
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

function IndeterminateCheckbox({
  checked,
  indeterminate,
  onChange,
  className,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: () => void;
  className?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      onClick={(e) => e.stopPropagation()}
      className={cn('cursor-pointer rounded accent-workspace-accent', className)}
    />
  );
}

function IndividualDetailPanel({
  instance,
  detail,
  loading,
  graphUri,
  workspaceId,
  onPropertyDeleted,
  onIndividualDeleted,
}: {
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

  const classUri = detail?.class_uri || instance.class_uri;
  const dataProperties = detail?.data_properties ?? [];
  const canAddProperties = datatypeProperties.length > 0 && !datatypePropertiesLoading;

  useEffect(() => {
    if (!classUri) {
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
  }, [workspaceId, classUri, graphUri]);

  useEffect(() => {
    if (datatypeProperties.length > 0 && !newPredicateUri) {
      setNewPredicateUri(datatypeProperties[0].uri);
    }
  }, [datatypeProperties, newPredicateUri]);

  useEffect(() => {
    if (!classUri) {
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
  }, [workspaceId, classUri]);

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
  }, [instance.uri]);

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
      await authFetch(`${getApiUrl()}/api/graph/nodes/data-property/delete`, {
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
      await authFetch(`${getApiUrl()}/api/graph/nodes/data-property/update`, {
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
      await authFetch(`${getApiUrl()}/api/graph/nodes/object-property/update`, {
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
      const res = await authFetch(`${getApiUrl()}/api/graph/nodes/object-property/add`, {
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
      await authFetch(`${getApiUrl()}/api/graph/nodes/object-property/delete`, {
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
      const res = await authFetch(`${getApiUrl()}/api/graph/nodes/data-property/add`, {
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
      await authFetch(`${getApiUrl()}/api/graph/nodes/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          graph_uri: graphUri,
          individual_uri: instance.uri,
        }),
      });
      onIndividualDeleted();
    } finally {
      setDeletingIndividual(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      {confirmDialog}

      <div className="mb-6">
        <div className="mb-2 flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-orange-100 dark:bg-orange-900/30">
            <Circle size={20} className="text-orange-500" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold">{instanceLabel(instance)}</h2>
            <p className="truncate font-mono text-xs text-muted-foreground" title={instance.uri}>
              {instance.uri}
            </p>
          </div>
          <button
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
          </button>
        </div>
        <div className="ml-13 flex items-center gap-2">
          <Box size={14} className="text-blue-500" />
          <span className="text-sm text-muted-foreground">
            {instance.class_label || compactUri(instance.class_uri)}
          </span>
        </div>
      </div>

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
              Data Properties
              <span className="text-xs text-muted-foreground">({dataProperties.length})</span>
            </h3>

            {dataProperties.length === 0 ? (
              <p className="mb-3 rounded-lg border p-4 text-center text-sm text-muted-foreground">
                No data properties yet. Add one below.
              </p>
            ) : (
              <div className="mb-3 space-y-2">
                {dataProperties.map((dp, i) => {
                  const rowKey = dataPropertyRowKey(dp.predicate_uri, dp.value, i);
                  const isDeleting = deletingKeys.has(rowKey);
                  const isSaving = savingKeys.has(rowKey);
                  const isEditing = editingKey === rowKey;
                  return (
                    <div
                      key={rowKey}
                      className="flex items-start gap-3 rounded-lg border bg-background px-4 py-2.5 text-sm"
                    >
                      <div className="w-2/5 shrink-0 pt-0.5 font-medium text-purple-600 dark:text-purple-400">
                        {dp.predicate_label}
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
                      {!isEditing && (
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
              <div className="mb-3 space-y-2">
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

            <div className="rounded-lg border border-dashed bg-muted/10 p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-sm font-medium">Add data property</p>
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
            </div>
          </div>

          <div>
            <h3 className="mb-3 flex items-center gap-2 font-medium">
              <Link2 size={16} className="text-green-500" />
              Object Properties
              <span className="text-xs text-muted-foreground">({objectProperties.length})</span>
            </h3>

            {objectProperties.length === 0 ? (
              <p className="mb-3 rounded-lg border p-4 text-center text-sm text-muted-foreground">
                No object properties yet. Add one below.
              </p>
            ) : (
              <div className="mb-3 space-y-2">
                {objectProperties.map((op, i) => {
                  const rowKey = objectPropertyRowKey(op.predicate_uri, op.targetId, i);
                  const isDeleting = deletingKeys.has(rowKey);
                  const isSaving = savingKeys.has(rowKey);
                  const isEditing = editingRelationKey === rowKey;
                  const editingProperty = findRelationProperty(editingPredicateUri);
                  return (
                    <div
                      key={rowKey}
                      className="rounded-lg border bg-background px-4 py-2.5 text-sm"
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
                          <div className="w-2/5 shrink-0 pt-0.5 font-medium text-green-600 dark:text-green-400">
                            {op.predicate}
                          </div>
                          <div className="min-w-0 flex-1">
                            <span className="font-medium">{op.targetLabel}</span>
                            {op.targetLabel !== op.targetId && (
                              <span
                                className="mt-0.5 block truncate font-mono text-xs text-muted-foreground"
                                title={op.targetId}
                              >
                                {op.targetId}
                              </span>
                            )}
                          </div>
                          <div className="flex shrink-0 items-center gap-1">
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
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {relationDraftRows.length > 0 && (
              <div className="mb-3 space-y-2">
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

            <div className="rounded-lg border border-dashed bg-muted/10 p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-sm font-medium">Add relation</p>
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
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BatchTablePanel({
  instances,
  graphUri,
  workspaceId,
  onDeleted,
}: {
  instances: ApiDiscoveryInstance[];
  graphUri: string;
  workspaceId: string;
  onDeleted: (deletedUris: string[]) => void;
}) {
  const [rowChecked, setRowChecked] = useState<Set<string>>(
    () => new Set(instances.map((i) => i.uri))
  );
  const [showDialog, setShowDialog] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setRowChecked(new Set(instances.map((i) => i.uri)));
  }, [instances]);

  const allChecked =
    instances.length > 0 && instances.every((i) => rowChecked.has(i.uri));
  const someChecked = !allChecked && instances.some((i) => rowChecked.has(i.uri));
  const checkedCount = rowChecked.size;

  const headerCheckRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (headerCheckRef.current) headerCheckRef.current.indeterminate = someChecked;
  }, [someChecked]);

  const toggleAll = () => {
    if (allChecked || someChecked) setRowChecked(new Set());
    else setRowChecked(new Set(instances.map((i) => i.uri)));
  };

  const toggleRow = (uri: string) => {
    setRowChecked((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  };

  const handleBatchDelete = async () => {
    setDeleting(true);
    setShowDialog(false);
    setConfirmInput('');
    const uris = [...rowChecked];
    const deletedUris: string[] = [];
    for (const uri of uris) {
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/nodes/delete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: graphUri,
            individual_uri: uri,
          }),
        });
        if (res.ok) deletedUris.push(uri);
      } catch {
        // continue with remaining deletions
      }
    }
    setDeleting(false);
    onDeleted(deletedUris);
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border bg-background p-6 shadow-2xl">
            <h3 className="text-base font-semibold">
              Remove {checkedCount} individual{checkedCount !== 1 ? 's' : ''}?
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              This will permanently remove {checkedCount} individual
              {checkedCount !== 1 ? 's' : ''} and all their triples from the graph. This action
              cannot be undone.
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              Type{' '}
              <span className="font-semibold text-foreground">{checkedCount}</span> to confirm:
            </p>
            <input
              autoFocus
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && confirmInput === String(checkedCount))
                  void handleBatchDelete();
                if (e.key === 'Escape') {
                  setShowDialog(false);
                  setConfirmInput('');
                }
              }}
              className="mt-2 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              placeholder={`Type ${checkedCount} to confirm`}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowDialog(false);
                  setConfirmInput('');
                }}
                className="px-4 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={confirmInput !== String(checkedCount)}
                onClick={() => void handleBatchDelete()}
                className="bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Remove {checkedCount} individual{checkedCount !== 1 ? 's' : ''}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex shrink-0 items-center gap-3 border-b px-4 py-2">
        <span className="text-sm font-semibold">
          {instances.length} individual{instances.length !== 1 ? 's' : ''} selected
        </span>
        <div className="ml-auto">
          {deleting ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 size={14} className="animate-spin" />
              Removing…
            </div>
          ) : (
            <button
              type="button"
              disabled={checkedCount === 0}
              onClick={() => setShowDialog(true)}
              className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs text-red-500 transition-colors hover:bg-red-50 disabled:opacity-50 dark:hover:bg-red-900/20"
            >
              <Trash2 size={12} />
              Remove {checkedCount} selected
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-muted/40">
            <tr>
              <th className="w-10 px-3 py-2 text-left">
                <input
                  ref={headerCheckRef}
                  type="checkbox"
                  checked={allChecked}
                  onChange={toggleAll}
                  className="h-4 w-4 cursor-pointer rounded accent-workspace-accent"
                />
              </th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">URI</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Label</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Class</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">Bucket</th>
              <th
                className="px-3 py-2 text-right font-medium text-muted-foreground"
                title="Outgoing object properties (domain)"
              >
                →
              </th>
              <th
                className="px-3 py-2 text-right font-medium text-muted-foreground"
                title="Incoming object properties (range)"
              >
                ←
              </th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                Properties
              </th>
            </tr>
          </thead>
          <tbody>
            {instances.map((inst) => {
              const checked = rowChecked.has(inst.uri);
              return (
                <tr
                  key={inst.uri}
                  className={cn(
                    'border-t transition-colors',
                    checked
                      ? 'bg-orange-50/50 dark:bg-orange-900/10'
                      : 'hover:bg-muted/30'
                  )}
                >
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRow(inst.uri)}
                      className="h-4 w-4 cursor-pointer rounded accent-workspace-accent"
                    />
                  </td>
                  <td
                    className="max-w-[180px] truncate px-3 py-2 font-mono text-xs text-muted-foreground"
                    title={inst.uri}
                  >
                    {compactUri(inst.uri)}
                  </td>
                  <td
                    className="max-w-[180px] truncate px-3 py-2 font-medium"
                    title={instanceLabel(inst)}
                  >
                    {instanceLabel(inst)}
                  </td>
                  <td
                    className="max-w-[140px] truncate px-3 py-2 text-blue-600 dark:text-blue-400"
                    title={inst.class_label || inst.class_uri}
                  >
                    {inst.class_label || compactUri(inst.class_uri)}
                  </td>
                  <td
                    className="max-w-[120px] truncate px-3 py-2 text-muted-foreground"
                    title={inst.bfo_bucket_label ?? ''}
                  >
                    {inst.bfo_bucket_label ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {inst.domain_relations_count ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {inst.range_relations_count ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {inst.properties_count ?? '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function IndividualsPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = params.workspaceId as string;
  const preSelectedUri = searchParams?.get('selected') ?? null;
  const preSelectedClassUri = searchParams?.get('class') ?? null;
  const { selectedGraphId, visibleGraphIds, selectGraph } = useKnowledgeGraphStore();

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);

  const [classes, setClasses] = useState<ApiDiscoveryClass[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);
  const [selectedClassUris, setSelectedClassUris] = useState<string[]>([]);
  const lastSeededGraphUriRef = useRef<string | null>(null);

  const [selectedBucketUris, setSelectedBucketUris] = useState<string[]>(
    BFO_BUCKET_DEFS.filter((b) => b.uri).map((b) => b.uri)
  );

  const [search, setSearch] = useState('');
  // Search submitted on Enter. The /instances fetch reads this — typing alone
  // does not trigger a backend call.
  const [submittedSearch, setSubmittedSearch] = useState('');
  const SEARCH_MIN_CHARS = 2;
  const handleSubmitSearch = useCallback((raw: string) => {
    const trimmed = raw.trim();
    setSubmittedSearch(trimmed.length >= SEARCH_MIN_CHARS ? trimmed : '');
  }, []);
  const [instances, setInstances] = useState<ApiDiscoveryInstance[]>([]);
  const [instancesLoading, setInstancesLoading] = useState(false);
  const [instancesError, setInstancesError] = useState<string | null>(null);

  const [selectedIndividualUri, setSelectedIndividualUri] = useState<string | null>(null);
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [checkedUris, setCheckedUris] = useState<Set<string>>(new Set());

  const [instanceDetail, setInstanceDetail] = useState<InstanceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailRefreshTick, setDetailRefreshTick] = useState(0);
  const autoExpandedForRef = useRef<string | null>(null);
  const prevActiveGraphUriRef = useRef<string | null>(null);

  const allGraphs = useMemo<ApiGraphInfo[]>(() => {
    const seen = new Set<string>();
    const out: ApiGraphInfo[] = [];
    for (const pack of graphPacks) {
      for (const g of pack.graphs) {
        if (seen.has(g.uri)) continue;
        seen.add(g.uri);
        out.push(g);
      }
    }
    return out;
  }, [graphPacks]);

  const activeGraph = useMemo<ApiGraphInfo | null>(() => {
    if (selectedGraphId) {
      const match = allGraphs.find((g) => g.id === selectedGraphId);
      if (match) return match;
    }
    if (visibleGraphIds.length > 0) {
      const match = allGraphs.find((g) => visibleGraphIds.includes(g.id));
      if (match) return match;
    }
    return allGraphs.find((g) => !isSystemGraph(g)) ?? allGraphs[0] ?? null;
  }, [allGraphs, selectedGraphId, visibleGraphIds]);

  const bucketOptions = useMemo(
    () =>
      BFO_BUCKET_DEFS.filter((b) => b.uri).map((bucket) => ({
        uri: bucket.uri,
        label: bucket.label,
        hint: bucket.type,
      })),
    []
  );

  const allClassesSelected = useMemo(
    () =>
      classes.length > 0 &&
      selectedClassUris.length === classes.length &&
      classes.every((cls) => selectedClassUris.includes(cls.uri)),
    [classes, selectedClassUris],
  );

  // Show results only after the user submits a search (Enter, ≥ SEARCH_MIN_CHARS)
  // or ticks at least one class.
  const hasActiveFilter = submittedSearch.length > 0 || selectedClassUris.length > 0;

  const classUrisToFetch = useMemo(() => {
    if (!hasActiveFilter) return [];
    // All classes selected, or graph-wide search with no class filter
    if (allClassesSelected || (submittedSearch.length > 0 && selectedClassUris.length === 0)) {
      return [];
    }
    return selectedClassUris;
  }, [hasActiveFilter, allClassesSelected, submittedSearch, selectedClassUris]);

  const loadGraphs = useCallback(async () => {
    setGraphsLoading(true);
    setGraphsError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!res.ok) throw new Error(`Failed to load graphs (${res.status})`);
      const data = (await res.json()) as ApiGraphPack[];
      setGraphPacks(Array.isArray(data) ? data : []);
    } catch (err) {
      setGraphsError(err instanceof Error ? err.message : 'Failed to load graphs');
      setGraphPacks([]);
    } finally {
      setGraphsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadGraphs();
  }, [loadGraphs]);

  // Pre-select individual from URL ?selected= param
  useEffect(() => {
    if (preSelectedUri) setSelectedIndividualUri(preSelectedUri);
  }, [preSelectedUri]);

  // Pre-select class from URL ?class= param (e.g. after creating an individual)
  useEffect(() => {
    if (!preSelectedClassUri) return;
    setSelectedClassUris((prev) =>
      prev.includes(preSelectedClassUri) ? prev : [...prev, preSelectedClassUri]
    );
  }, [preSelectedClassUri]);

  useEffect(() => {
    if (!activeGraph) {
      setClasses([]);
      return;
    }
    const graphChanged =
      prevActiveGraphUriRef.current !== null &&
      prevActiveGraphUriRef.current !== activeGraph.uri;
    prevActiveGraphUriRef.current = activeGraph.uri;
    if (graphChanged) {
      setExpandedClasses(new Set());
      setSelectedIndividualUri(null);
      setCheckedUris(new Set());
    }
    let cancelled = false;
    (async () => {
      setClassesLoading(true);
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/graph/discovery/classes?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = (await res.json()) as ApiDiscoveryClass[];
        if (!cancelled) {
          setClasses(data);
          if (lastSeededGraphUriRef.current !== activeGraph.uri) {
            lastSeededGraphUriRef.current = activeGraph.uri;
            // Do not auto-select classes — user must explicitly filter
            setSelectedBucketUris(BFO_BUCKET_DEFS.filter((b) => b.uri).map((b) => b.uri));
          }
        }
      } catch {
        if (!cancelled) setClasses([]);
      } finally {
        if (!cancelled) setClassesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeGraph, workspaceId]);

  useEffect(() => {
    if (!activeGraph || !hasActiveFilter) {
      setInstances([]);
      setInstancesLoading(false);
      setInstancesError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setInstancesLoading(true);
      setInstancesError(null);
      try {
        const res = await authFetch(`${getApiUrl()}/api/graph/discovery/instances`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            workspace_id: workspaceId,
            graph_uri: activeGraph.uri,
            class_uris: classUrisToFetch,
            property_uris: [RDFS_LABEL],
            search: submittedSearch,
          }),
        });
        if (!res.ok) throw new Error(`Search failed (${res.status})`);
        const data = (await res.json()) as ApiDiscoveryInstance[];
        if (!cancelled) {
          setInstances(data);
          setSelectedIndividualUri((prev) => {
            const target = preSelectedUri ?? prev;
            if (!target) return null;
            if (data.some((d) => d.uri === target)) return target;
            return preSelectedUri === target ? target : null;
          });
        }
      } catch (err) {
        if (!cancelled) {
          setInstancesError(err instanceof Error ? err.message : 'Search failed');
          setInstances([]);
        }
      } finally {
        if (!cancelled) setInstancesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    activeGraph,
    workspaceId,
    selectedClassUris,
    submittedSearch,
    hasActiveFilter,
    classUrisToFetch,
    preSelectedUri,
  ]);

  const filteredInstances = useMemo(() => {
    if (selectedBucketUris.length === 0) return [];
    const bucketSet = new Set(selectedBucketUris);
    return instances.filter((i) => !i.bfo_bucket_uri || bucketSet.has(i.bfo_bucket_uri));
  }, [instances, selectedBucketUris]);

  const checkedInstances = useMemo(
    () => filteredInstances.filter((i) => checkedUris.has(i.uri)),
    [filteredInstances, checkedUris]
  );

  const instancesByClass = useMemo(() => {
    const grouped = new Map<string, ApiDiscoveryInstance[]>();
    for (const inst of filteredInstances) {
      const cls = inst.class_label || compactUri(inst.class_uri) || 'Unknown';
      if (!grouped.has(cls)) grouped.set(cls, []);
      grouped.get(cls)!.push(inst);
    }
    return new Map([...grouped.entries()].sort((a, b) => a[0].localeCompare(b[0])));
  }, [filteredInstances]);

  const classSectionKeys = useMemo(
    () => [...instancesByClass.keys()].join('\0'),
    [instancesByClass],
  );

  // Auto-expand class sections when search or class filters are active
  useEffect(() => {
    if (!hasActiveFilter || !classSectionKeys) return;
    setExpandedClasses(new Set(classSectionKeys.split('\0')));
  }, [
    hasActiveFilter,
    classSectionKeys,
    submittedSearch,
    selectedClassUris.join(','),
    allClassesSelected,
    activeGraph?.uri,
  ]);

  // Auto-expand the class section containing the pre-selected individual
  useEffect(() => {
    if (!selectedIndividualUri || autoExpandedForRef.current === selectedIndividualUri) return;
    for (const [cls, insts] of instancesByClass) {
      if (insts.some((i) => i.uri === selectedIndividualUri)) {
        autoExpandedForRef.current = selectedIndividualUri;
        setExpandedClasses((prev) => new Set(prev).add(cls));
        break;
      }
    }
  }, [instancesByClass, selectedIndividualUri]);

  const selectedInstance = useMemo(() => {
    if (!selectedIndividualUri) return null;
    const found = filteredInstances.find((i) => i.uri === selectedIndividualUri);
    if (found) return found;
    if (instanceDetail?.uri === selectedIndividualUri) {
      return {
        uri: instanceDetail.uri,
        label: instanceDetail.label,
        class_uri: instanceDetail.class_uri,
        class_label: instanceDetail.class_label,
        properties: {},
      } satisfies ApiDiscoveryInstance;
    }
    return {
      uri: selectedIndividualUri,
      label: compactUri(selectedIndividualUri),
      class_uri: preSelectedClassUri ?? '',
      class_label: '',
      properties: {},
    } satisfies ApiDiscoveryInstance;
  }, [filteredInstances, selectedIndividualUri, instanceDetail, preSelectedClassUri]);

  useEffect(() => {
    if (!activeGraph || !selectedIndividualUri) {
      setInstanceDetail(null);
      setDetailLoading(false);
      return;
    }
    let cancelled = false;
    setInstanceDetail(null);
    setDetailLoading(true);
    void authFetch(`${getApiUrl()}/api/graph/discovery/instance-detail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspace_id: workspaceId,
        graph_uri: activeGraph.uri,
        instance_uri: selectedIndividualUri,
      }),
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => {
        if (!cancelled) setInstanceDetail(data as InstanceDetail);
      })
      .catch(() => {
        if (!cancelled) setInstanceDetail(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeGraph, workspaceId, selectedIndividualUri, detailRefreshTick]);

  const handlePropertyDeleted = useCallback(() => {
    setDetailRefreshTick((t) => t + 1);
  }, []);

  const handleIndividualDeleted = useCallback(() => {
    if (selectedIndividualUri) {
      setCheckedUris((prev) => {
        const next = new Set(prev);
        next.delete(selectedIndividualUri);
        return next;
      });
    }
    setInstances((prev) => prev.filter((i) => i.uri !== selectedIndividualUri));
    setSelectedIndividualUri(null);
  }, [selectedIndividualUri]);

  const handleBatchDeleted = useCallback((deletedUris: string[]) => {
    const deletedSet = new Set(deletedUris);
    setInstances((prev) => prev.filter((i) => !deletedSet.has(i.uri)));
    setCheckedUris((prev) => {
      const next = new Set(prev);
      for (const uri of deletedUris) next.delete(uri);
      return next;
    });
    setSelectedIndividualUri((prev) => (prev && deletedSet.has(prev) ? null : prev));
  }, []);

  const toggleClass = (uri: string) => {
    setSelectedClassUris((prev) =>
      prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
    );
  };

  const toggleBucket = (uri: string) => {
    setSelectedBucketUris((prev) =>
      prev.includes(uri) ? prev.filter((u) => u !== uri) : [...prev, uri]
    );
  };

  const toggleClassSection = (cls: string) => {
    setExpandedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  };

  const toggleChecked = (uri: string) => {
    setCheckedUris((prev) => {
      const next = new Set(prev);
      if (next.has(uri)) next.delete(uri);
      else next.add(uri);
      return next;
    });
  };

  const toggleClassChecked = (classInstances: ApiDiscoveryInstance[]) => {
    const uris = classInstances.map((i) => i.uri);
    const allInChecked = uris.every((u) => checkedUris.has(u));
    setCheckedUris((prev) => {
      const next = new Set(prev);
      if (allInChecked) uris.forEach((u) => next.delete(u));
      else uris.forEach((u) => next.add(u));
      return next;
    });
  };

  const toggleAllFiltered = () => {
    const allChecked =
      filteredInstances.length > 0 && filteredInstances.every((i) => checkedUris.has(i.uri));
    if (allChecked) {
      setCheckedUris(new Set());
    } else {
      setCheckedUris(new Set(filteredInstances.map((i) => i.uri)));
    }
  };

  const handleGraphChange = (graph: ApiGraphInfo) => {
    selectGraph(graph.id);
  };

  const allFilteredChecked =
    filteredInstances.length > 0 && filteredInstances.every((i) => checkedUris.has(i.uri));
  const someFilteredChecked =
    !allFilteredChecked && filteredInstances.some((i) => checkedUris.has(i.uri));

  const selectAllRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someFilteredChecked;
  }, [someFilteredChecked]);

  const openCreateIndividual = () => {
    router.push(`/workspace/${workspaceId}/graph/create-individual`);
  };

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <GraphDevBanner />

          <div className="flex min-h-0 flex-1 overflow-hidden bg-card">
            {graphsLoading ? (
              <div className="flex flex-1 items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : graphsError ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="mb-2 text-sm">{graphsError}</p>
                  <button
                    type="button"
                    onClick={() => void loadGraphs()}
                    className="mx-auto flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    <RefreshCw size={14} />
                    Retry
                  </button>
                </div>
              </div>
            ) : !activeGraph ? (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-sm text-muted-foreground">No graphs available in this workspace.</p>
              </div>
            ) : (
              <>
                {/* Left panel */}
                <div className="flex w-[30rem] shrink-0 flex-col border-r bg-muted/20">
                  <div className="border-b p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Users size={18} className="text-orange-500 dark:text-orange-400" />
                      <h2 className="font-semibold">Individuals</h2>
                      {hasActiveFilter && (
                        <span className="text-xs text-muted-foreground">
                          ({filteredInstances.length.toLocaleString()})
                        </span>
                      )}
                      {hasActiveFilter && filteredInstances.length > 0 && (
                        <div className="ml-auto flex items-center gap-1.5">
                          <input
                            ref={selectAllRef}
                            type="checkbox"
                            checked={allFilteredChecked}
                            onChange={toggleAllFiltered}
                            className="h-4 w-4 cursor-pointer rounded accent-workspace-accent"
                            title="Select all visible individuals"
                          />
                          {checkedUris.size > 0 && (
                            <span className="text-xs text-muted-foreground">
                              {checkedUris.size} selected
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="relative mb-3">
                      <Search
                        size={14}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                      />
                      <input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleSubmitSearch(search);
                          }
                        }}
                        placeholder="Search individuals — press Enter"
                        className="w-full rounded-md border bg-background py-1.5 pl-8 pr-8 text-sm outline-none focus:ring-2 focus:ring-primary"
                      />
                      {(search || submittedSearch) && (
                        <button
                          type="button"
                          onClick={() => {
                            setSearch('');
                            handleSubmitSearch('');
                          }}
                          title="Clear search"
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>

                    <div className="flex flex-col gap-2">
                      <div className="flex gap-2">
                        <div className="flex-1">
                          <CheckboxFilter
                            label="Graph"
                            loading={graphsLoading}
                            options={allGraphs.map((g) => ({
                              uri: g.uri,
                              label: g.label,
                              hint: g.role_label,
                            }))}
                            selected={activeGraph ? [activeGraph.uri] : []}
                            onToggle={(uri) => {
                              if (uri !== activeGraph?.uri) {
                                const g = allGraphs.find((gr) => gr.uri === uri);
                                if (g) handleGraphChange(g);
                              }
                            }}
                            onSetSelected={(uris) => {
                              const newUri = uris.find((u) => u !== activeGraph?.uri) ?? uris[0];
                              if (newUri) {
                                const g = allGraphs.find((gr) => gr.uri === newUri);
                                if (g) handleGraphChange(g);
                              }
                            }}
                            emptyMessage="No graphs available."
                          />
                        </div>
                        <div className="flex-1">
                          <CheckboxFilter
                            label="Buckets"
                            options={bucketOptions}
                            selected={selectedBucketUris}
                            onToggle={toggleBucket}
                            onSetSelected={setSelectedBucketUris}
                            emptyMessage="No buckets available."
                          />
                        </div>
                      </div>

                      <CheckboxFilter
                        label="Classes"
                        loading={classesLoading}
                        options={classes.map((cls) => ({
                          uri: cls.uri,
                          label: cls.label || compactUri(cls.uri),
                          hint: String(cls.count),
                        }))}
                        selected={selectedClassUris}
                        onToggle={toggleClass}
                        onSetSelected={setSelectedClassUris}
                        emptyMessage="No classes found."
                        emptySummary="Select a class"
                      />
                    </div>
                  </div>

                  {instancesError && (
                    <div className="border-b bg-destructive/10 px-4 py-2 text-xs text-destructive">
                      {instancesError}
                    </div>
                  )}

                  <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
                    {!hasActiveFilter ? (
                      <p className="px-2 py-8 text-center text-sm text-muted-foreground">
                        Type a search and press Enter, or select one or more classes (use
                        Select all) to display results.
                      </p>
                    ) : instancesLoading && filteredInstances.length === 0 ? (
                      <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
                        <Loader2 size={16} className="animate-spin" />
                        <span className="text-sm">Loading…</span>
                      </div>
                    ) : instancesByClass.size === 0 ? (
                      <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                        No individuals found.
                      </p>
                    ) : (
                      Array.from(instancesByClass.entries()).map(([cls, classInstances]) => {
                        const isExpanded = expandedClasses.has(cls);
                        const classAllChecked = classInstances.every((i) =>
                          checkedUris.has(i.uri)
                        );
                        const classSomeChecked =
                          !classAllChecked && classInstances.some((i) => checkedUris.has(i.uri));
                        const sorted = [...classInstances].sort((a, b) =>
                          instanceLabel(a).localeCompare(instanceLabel(b), undefined, {
                            sensitivity: 'base',
                          })
                        );
                        return (
                          <div key={cls}>
                            <div className="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-sm hover:bg-background">
                              <IndeterminateCheckbox
                                checked={classAllChecked}
                                indeterminate={classSomeChecked}
                                onChange={() => toggleClassChecked(classInstances)}
                                className="h-3.5 w-3.5 shrink-0"
                              />
                              <button
                                type="button"
                                onClick={() => toggleClassSection(cls)}
                                className="flex flex-1 items-center gap-1 text-left"
                              >
                                <ChevronRight
                                  size={14}
                                  className={cn(
                                    'shrink-0 text-muted-foreground transition-transform',
                                    isExpanded && 'rotate-90'
                                  )}
                                />
                                <Box size={14} className="shrink-0 text-blue-500" />
                                <span className="flex-1 truncate font-medium">{cls}</span>
                                <span className="text-xs text-muted-foreground">
                                  {classInstances.length}
                                </span>
                              </button>
                            </div>

                            {isExpanded &&
                              sorted.map((ind) => (
                                <div
                                  key={ind.uri}
                                  className={cn(
                                    'flex w-full items-center gap-2 rounded-md py-1 pl-7 pr-2 text-sm transition-colors',
                                    checkedUris.has(ind.uri)
                                      ? 'bg-orange-50/60 dark:bg-orange-900/10'
                                      : 'hover:bg-background'
                                  )}
                                >
                                  <input
                                    type="checkbox"
                                    checked={checkedUris.has(ind.uri)}
                                    onChange={() => toggleChecked(ind.uri)}
                                    onClick={(e) => e.stopPropagation()}
                                    className="h-3.5 w-3.5 shrink-0 cursor-pointer rounded accent-workspace-accent"
                                  />
                                  <button
                                    type="button"
                                    onClick={() => setSelectedIndividualUri(ind.uri)}
                                    title={ind.uri}
                                    className={cn(
                                      'flex flex-1 items-center gap-2 text-left',
                                      selectedIndividualUri === ind.uri
                                        ? 'text-workspace-accent'
                                        : ''
                                    )}
                                  >
                                    <Circle
                                      size={10}
                                      className="shrink-0 text-orange-500 dark:text-orange-400"
                                    />
                                    <span className="truncate">{instanceLabel(ind)}</span>
                                  </button>
                                </div>
                              ))}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* Center panel */}
                <div className="flex flex-1 overflow-hidden">
                  {checkedInstances.length >= 2 ? (
                    <BatchTablePanel
                      instances={checkedInstances}
                      graphUri={activeGraph.uri}
                      workspaceId={workspaceId}
                      onDeleted={handleBatchDeleted}
                    />
                  ) : selectedInstance ? (
                    <IndividualDetailPanel
                      instance={selectedInstance}
                      detail={instanceDetail}
                      loading={detailLoading}
                      graphUri={activeGraph.uri}
                      workspaceId={workspaceId}
                      onPropertyDeleted={handlePropertyDeleted}
                      onIndividualDeleted={handleIndividualDeleted}
                    />
                  ) : (
                    <div className="flex flex-1 items-center justify-center">
                      <div className="text-center">
                        <div className="mb-4 flex justify-center">
                          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                            <Users size={32} className="text-orange-500 dark:text-orange-400" />
                          </div>
                        </div>
                        <h2 className="mb-2 text-lg font-semibold">Individuals</h2>
                        <p className="mb-6 max-w-md text-muted-foreground">
                          Select an individual from the left panel to view its data and object
                          properties, or create a new individual.
                        </p>
                        <div className="flex justify-center">
                          <button
                            type="button"
                            onClick={openCreateIndividual}
                            className={cn(
                              'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                              'hover:opacity-90'
                            )}
                          >
                            <UserPlus size={16} />
                            New Individual
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
