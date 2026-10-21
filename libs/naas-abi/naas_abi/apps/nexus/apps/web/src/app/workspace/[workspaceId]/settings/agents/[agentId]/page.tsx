'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Bot, CheckCircle, Save, XCircle } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { getLogoUrl } from '@/lib/logo-url';
import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Textarea } from '@/components/ui/input';
import {
  SettingsEmpty,
  SettingsField,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
} from '@/components/settings/settings-ui';

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
  enabled: boolean;
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

export default function AgentEditPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const agentId = params.agentId as string;

  const { agents, fetchAgents, updateAgent, toggleAgent } = useAgentsStore();
  const { refreshProviders } = useIntegrationsStore();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [serviceAgent, setServiceAgent] = useState<ServiceAgent | null>(null);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [provider, setProvider] = useState('');
  const [modelId, setModelId] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [enabled, setEnabled] = useState(false);

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
    const load = async () => {
      try {
        if (!workspaceId || !agentId) return;
        setLoading(true);
        setError(null);

        // Run the three loads in parallel; they are independent.
        const [response] = await Promise.all([
          authFetch(`${getApiUrl()}/api/agents/?workspace_id=${workspaceId}`),
          fetchAgents(workspaceId, true),
          refreshProviders(),
        ]);
        if (!response.ok) {
          throw new Error('Failed to load agent from service');
        }
        const serviceAgents = (await response.json()) as ServiceAgent[];
        const selectedServiceAgent = serviceAgents.find((agent) => agent.id === agentId) || null;
        if (!selectedServiceAgent) {
          setError('Agent not found in service');
          return;
        }

        setServiceAgent(selectedServiceAgent);
        setName(selectedServiceAgent.name || '');
        setDescription(selectedServiceAgent.description || '');
        setSystemPrompt(selectedServiceAgent.system_prompt || '');
        setProvider(selectedServiceAgent.provider || '');
        setModelId(selectedServiceAgent.model_id || '');
        setLogoUrl(selectedServiceAgent.logo_url || '');
        setEnabled(Boolean(selectedServiceAgent.enabled));

      } catch (err) {
        console.error(err);
        setError(err instanceof Error ? err.message : 'Failed to load agent');
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [workspaceId, agentId, fetchAgents, refreshProviders]);

  const handleSave = async () => {
    if (!storeAgent) return;
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await updateAgent(storeAgent.id, {
        name: name.trim(),
        description: description.trim(),
        systemPrompt,
        provider: provider || null,
        modelId: modelId || null,
        logoUrl: logoUrl || null,
      });
      if (storeAgent.enabled !== enabled) {
        await toggleAgent(storeAgent.id);
      }
      setSaved(true);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to save agent');
    } finally {
      setSaving(false);
    }
  };

  const backButton = (
    <Button variant="secondary" onClick={() => router.push(`/workspace/${workspaceId}/settings/agents`)}>
      <ArrowLeft size={16} />
      Back to agents
    </Button>
  );

  if (loading) {
    return <SettingsLoading label="Loading agent…" />;
  }

  if (error) {
    return (
      <div className="space-y-4">
        {backButton}
        <SettingsNotice tone="error" icon={<XCircle size={14} />}>
          {error}
        </SettingsNotice>
      </div>
    );
  }

  if (!storeAgent || !serviceAgent) {
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

  return (
    <div className="space-y-6">
      <div>{backButton}</div>
      <SettingsPageHeader
        leading={
          <div
            className={cn(
              'flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden',
              serviceAgent.logo_url ? 'bg-transparent' : 'bg-muted'
            )}
          >
            {serviceAgent.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={getLogoUrl(serviceAgent.logo_url)} alt={serviceAgent.name} className="h-full w-full object-cover" />
            ) : (
              <Bot size={16} />
            )}
          </div>
        }
        title="Edit Agent"
        description={serviceAgent.name}
        actions={
          <>
            <Checkbox
              checked={enabled}
              onCheckedChange={setEnabled}
              label="Enabled"
              title={enabled ? 'Disable agent' : 'Enable agent'}
            />
            <Button onClick={handleSave} disabled={saving}>
              <Save size={16} />
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </>
        }
      />

      {saved && (
        <SettingsNotice tone="success" icon={<CheckCircle size={14} />}>
          Agent updated
        </SettingsNotice>
      )}

      <SettingsSection title="General">
        <div className="space-y-4">
          <SettingsField label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </SettingsField>
          <SettingsField label="Description">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="resize-none" />
          </SettingsField>
          <SettingsField label="System Prompt">
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={12}
              className="min-h-[14rem] resize-y"
            />
          </SettingsField>
          <div className="grid grid-cols-2 gap-3">
            <SettingsField label="Provider">
              <Input value={provider} onChange={(e) => setProvider(e.target.value)} />
            </SettingsField>
            <SettingsField label="Model ID">
              <Input value={modelId} onChange={(e) => setModelId(e.target.value)} />
            </SettingsField>
          </div>
          <SettingsField label="Logo URL">
            <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} />
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
              ['Status', serviceAgent.enabled ? 'Enabled' : 'Disabled', false],
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
