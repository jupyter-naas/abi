'use client';

import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Bot, CheckCircle, Save, XCircle } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { getLogoUrl } from '@/lib/logo-url';
import { readAgentRoster, useAgentsStore } from '@/stores/agents';
import { useIntegrationsStore } from '@/stores/integrations';
import { Button } from '@/components/ui/button';
import { Input, Textarea } from '@/components/ui/input';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { Notice } from '@/components/ui/notice';
import { EmptyState } from '@/components/ui/empty-state';
import { Loading } from '@/components/ui/spinner';
import { Field } from '@/components/ui/field';
import { Card } from '@/components/ui/card';

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

export default function AgentEditPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const agentId = params.agentId as string;

  const { agents, updateAgent } = useAgentsStore();
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
        setName(selectedServiceAgent.name || '');
        setDescription(selectedServiceAgent.description || '');
        setSystemPrompt(selectedServiceAgent.system_prompt || '');
        setProvider(selectedServiceAgent.provider || '');
        setModelId(selectedServiceAgent.model_id || '');
        setLogoUrl(selectedServiceAgent.logo_url || '');

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
    return <Loading label="Loading agent…" />;
  }

  if (error) {
    return (
      <div className="space-y-4">
        {backButton}
        <Notice tone="error" icon={<XCircle size={14} />}>
          {error}
        </Notice>
      </div>
    );
  }

  if (!storeAgent || !serviceAgent) {
    return (
      <div className="space-y-4">
        {backButton}
        <EmptyState framed title="Agent not found." />
      </div>
    );
  }

  const listSection = (title: string, items: string[], empty: string, mono = true) => (
    <Card title={title}>
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
    </Card>
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
          <Button onClick={handleSave} disabled={saving}>
            <Save size={16} />
            {saving ? 'Saving...' : 'Save'}
          </Button>
        }
      />

      {saved && (
        <Notice tone="success" icon={<CheckCircle size={14} />}>
          Agent updated
        </Notice>
      )}

      <Card title="General">
        <div className="space-y-4">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Description">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="resize-none" />
          </Field>
          <Field label="System Prompt">
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={12}
              className="min-h-[14rem] resize-y"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Provider">
              <Input value={provider} onChange={(e) => setProvider(e.target.value)} />
            </Field>
            <Field label="Model ID">
              <Input value={modelId} onChange={(e) => setModelId(e.target.value)} />
            </Field>
          </div>
          <Field label="Logo URL">
            <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card title="Logo Preview">
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
      </Card>

      <Card title="Suggestions">
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
      </Card>

      <Card title="Intents">
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
      </Card>

      {listSection('Tools', tools, 'No tools configured')}
      {listSection('Subagents', subagents, 'No subagents configured')}

      <Card title="Service Metadata">
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
      </Card>
    </div>
  );
}
