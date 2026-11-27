'use client';

import { useEffect, useMemo, useState } from 'react';
import { XCircle } from 'lucide-react';
import { useParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getLogoUrl } from '@/lib/logo-url';
import { readAgentRoster, useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { usePageDraft } from '@/hooks/use-page-state';
import { Input, Textarea } from '@/components/ui/input';
import { InstanceHeader } from '@/components/access/instance-header';
import { FormSaveButton, InstanceBack, UnsavedBar } from '@/components/settings/instance-form';
import { ModuleLink } from '@/components/settings/module-link';
import {
  SettingsEmpty,
  SettingsField,
  SettingsLoading,
  SettingsNotice,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { agentModule } from '../agents-model';

type ServiceIntent = {
  intent_value: string;
  intent_type: string;
  intent_target: string;
  intent_scope?: string;
};

type ServiceSuggestion = {
  label: string;
  value: string;
};

type ServiceAgent = {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  class_name?: string | null;
  system_prompt?: string | null;
  model_id?: string | null;
  provider?: string | null;
  logo_url?: string | null;
  created_at: string;
  updated_at: string;
  suggestions?: ServiceSuggestion[] | null;
  intents?: ServiceIntent[] | null;
};

const FIELD_LABELS: Record<string, string> = {
  name: 'Name',
  description: 'Description',
  systemPrompt: 'System Prompt',
  provider: 'Provider',
  modelId: 'Model ID',
  logoUrl: 'Logo URL',
};

/**
 * An agent's page under Workspace settings › Agents: the header of an instance's page (its logo,
 * name, id, its module linked to Access › Modules), Save at its right, faded until something
 * changes, the unsaved bar; the edits are kept for a return to the page (`usePageDraft`).
 */
export default function AgentEditPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const agentId = params.agentId as string;

  const { agents, updateAgent } = useAgentsStore();
  const { refreshProviders } = useIntegrationsStore();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [serviceAgent, setServiceAgent] = useState<ServiceAgent | null>(null);

  // The agent as the service holds it, and the edits over it.
  const server = useMemo(
    () =>
      serviceAgent
        ? {
            name: serviceAgent.name || '',
            description: serviceAgent.description || '',
            systemPrompt: serviceAgent.system_prompt || '',
            provider: serviceAgent.provider || '',
            modelId: serviceAgent.model_id || '',
            logoUrl: serviceAgent.logo_url || '',
          }
        : null,
    [serviceAgent]
  );
  const draft = usePageDraft(
    workspaceId && agentId ? { scope: `workspace:${workspaceId}`, page: 'agents', detail: agentId } : null,
    server
  );
  const values = draft.values ?? server;
  const dirty = !!server && !!values && Object.keys(server).some((key) => server[key as keyof typeof server] !== values[key as keyof typeof values]);
  const set = (key: keyof NonNullable<typeof server>) => (value: string) => {
    setSaved(false);
    draft.set({ [key]: value });
  };

  const storeAgent = useMemo(() => agents.find((agent) => agent.id === agentId), [agents, agentId]);
  const tools = storeAgent?.tools ?? [];
  const subagents = useMemo(() => {
    if (!serviceAgent?.intents) return [];
    return serviceAgent.intents
      .filter((intent) => intent.intent_type?.toLowerCase() === 'agent')
      .map((intent) => intent.intent_target)
      .filter((target): target is string => Boolean(target));
  }, [serviceAgent]);

  useEffect(() => {
    // An answer for another agent or workspace (the page moved on) is dropped.
    let cancelled = false;
    const load = async () => {
      try {
        if (!workspaceId || !agentId) return;
        setLoading(true);
        setError(null);

        // One roster for the store and this page (reconciled when it is old); the
        // providers are independent and read meanwhile.
        const [roster] = await Promise.all([
          readAgentRoster(workspaceId).catch(() => {
            throw new Error('Failed to load agent from service');
          }),
          refreshProviders(),
        ]);
        if (cancelled) return;
        const serviceAgents = roster as ServiceAgent[];
        const selectedServiceAgent = serviceAgents.find((agent) => agent.id === agentId) || null;
        if (!selectedServiceAgent) {
          setError('Agent not found in service');
          return;
        }

        setServiceAgent(selectedServiceAgent);

      } catch (err) {
        if (cancelled) return;
        console.error(err);
        setError(err instanceof Error ? err.message : 'Failed to load agent');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, agentId, refreshProviders]);

  const handleSave = async () => {
    if (!storeAgent || !values || !serviceAgent) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const next = {
        name: values.name.trim(),
        description: values.description.trim(),
        systemPrompt: values.systemPrompt,
        provider: values.provider || null,
        modelId: values.modelId || null,
        logoUrl: values.logoUrl || null,
      };
      await updateAgent(storeAgent.id, next);
      // What the service now holds: the edits are no longer edits.
      setServiceAgent({
        ...serviceAgent,
        name: next.name,
        description: next.description,
        system_prompt: next.systemPrompt,
        provider: next.provider,
        model_id: next.modelId,
        logo_url: next.logoUrl,
      });
      draft.discard();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to save agent');
    } finally {
      setSaving(false);
    }
  };

  const backButton = <InstanceBack href={`/workspace/${workspaceId}/settings/agents`} label="agents" />;

  if (loading) {
    return <SettingsLoading label="Loading agent…" />;
  }

  if (error && !serviceAgent) {
    return (
      <div className="space-y-4">
        {backButton}
        <SettingsNotice tone="error" icon={<XCircle size={14} />}>
          {error}
        </SettingsNotice>
      </div>
    );
  }

  if (!storeAgent || !serviceAgent || !values) {
    return (
      <div className="space-y-4">
        {backButton}
        <SettingsEmpty title="Agent not found." />
      </div>
    );
  }

  const listSection = (title: string, items: string[], empty: string, mono = true) => (
    <SettingsSection title={title}>
      {items.length > 0 ? (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item} className={cn('bg-muted/50 px-2 py-1', mono ? 'font-mono text-xs' : 'text-sm')}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <XCircle size={14} />
          {empty}
        </p>
      )}
    </SettingsSection>
  );

  const moduleName = agentModule({ class_name: serviceAgent.class_name ?? undefined } as Parameters<typeof agentModule>[0]);

  return (
    <div className="space-y-6">
      {backButton}
      <InstanceHeader
        name={serviceAgent.name}
        id={serviceAgent.id}
        image={serviceAgent.logo_url ? getLogoUrl(serviceAgent.logo_url) : null}
        imageAlt={serviceAgent.name}
        meta={
          moduleName ? (
            <span>
              From the module <ModuleLink workspaceId={workspaceId} module={moduleName} />
            </span>
          ) : (
            <span>Built in this workspace</span>
          )
        }
        actions={<FormSaveButton dirty={dirty} saving={saving} saved={saved} onSave={() => void handleSave()} />}
      />

      {error && (
        <SettingsNotice tone="error" icon={<XCircle size={14} />}>
          {error}
        </SettingsNotice>
      )}
      <UnsavedBar
        show={dirty}
        conflicts={draft.conflicts.map((field) => FIELD_LABELS[field] ?? field)}
        onDiscard={draft.discard}
        disabled={saving}
      />

      <SettingsSection title="General">
        <div className="space-y-4">
          <SettingsField label="Name">
            <Input aria-label="Name" value={values.name} onChange={(e) => set('name')(e.target.value)} />
          </SettingsField>
          <SettingsField label="Description">
            <Textarea
              aria-label="Description"
              value={values.description}
              onChange={(e) => set('description')(e.target.value)}
              rows={3}
              className="resize-none"
            />
          </SettingsField>
          <SettingsField label="System Prompt">
            <Textarea
              aria-label="System Prompt"
              value={values.systemPrompt}
              onChange={(e) => set('systemPrompt')(e.target.value)}
              rows={12}
              className="min-h-[14rem] resize-y"
            />
          </SettingsField>
          <div className="grid grid-cols-2 gap-3">
            <SettingsField label="Provider">
              <Input aria-label="Provider" value={values.provider} onChange={(e) => set('provider')(e.target.value)} />
            </SettingsField>
            <SettingsField label="Model ID">
              <Input aria-label="Model ID" value={values.modelId} onChange={(e) => set('modelId')(e.target.value)} />
            </SettingsField>
          </div>
          <SettingsField label="Logo URL">
            <Input aria-label="Logo URL" value={values.logoUrl} onChange={(e) => set('logoUrl')(e.target.value)} />
          </SettingsField>
        </div>
      </SettingsSection>

      <SettingsSection title="Logo Preview">
        {serviceAgent.logo_url ? (
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 overflow-hidden border border-border bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={getLogoUrl(serviceAgent.logo_url)} alt={serviceAgent.name} className="h-full w-full object-cover" />
            </div>
            <p className="break-all text-xs text-muted-foreground">{serviceAgent.logo_url}</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No logo defined</p>
        )}
      </SettingsSection>

      <SettingsSection title="Suggestions">
        {serviceAgent.suggestions && serviceAgent.suggestions.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {serviceAgent.suggestions.map((suggestion) => (
              <li key={`${suggestion.label}-${suggestion.value}`} className="bg-muted/50 px-2 py-1">
                <span className="font-medium">{suggestion.label}</span>
                <span className="text-muted-foreground"> - {suggestion.value}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No suggestions</p>
        )}
      </SettingsSection>

      <SettingsSection title="Intents">
        {serviceAgent.intents && serviceAgent.intents.length > 0 ? (
          <div className="space-y-2">
            {serviceAgent.intents.map((intent, index) => (
              <div key={`${intent.intent_value}-${index}`} className="bg-muted/50 px-2 py-2 text-xs">
                <p><span className="text-muted-foreground">Value:</span> {intent.intent_value || '-'}</p>
                <p><span className="text-muted-foreground">Type:</span> {intent.intent_type || '-'}</p>
                <p><span className="text-muted-foreground">Target:</span> {intent.intent_target || '-'}</p>
                <p><span className="text-muted-foreground">Scope:</span> {intent.intent_scope || '-'}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <XCircle size={14} />
            No intents
          </p>
        )}
      </SettingsSection>

      {listSection('Tools', tools, 'No tools configured')}
      {listSection('Subagents', subagents, 'No subagents configured')}

      <SettingsSection title="Service Metadata">
        <dl className="grid grid-cols-2 gap-3 text-sm">
          {(
            [
              ['ID', serviceAgent.id, true],
              ['Workspace', serviceAgent.workspace_id, true],
              ['Class', serviceAgent.class_name || 'None', true],
              ['Provider', serviceAgent.provider || 'None', false],
              ['Model', serviceAgent.model_id || 'None', false],
              ['Created', new Date(serviceAgent.created_at).toLocaleString(), false],
              ['Updated', new Date(serviceAgent.updated_at).toLocaleString(), false],
            ] as const
          ).map(([label, value, mono]) => (
            <div key={label}>
              <dt className="text-muted-foreground">{label}</dt>
              <dd className={cn(mono && 'break-all font-mono text-xs')}>{value}</dd>
            </div>
          ))}
        </dl>
      </SettingsSection>
    </div>
  );
}
