'use client';

/**
 * Workspace settings › Agents › Create agent: a page, as Create workspace is, with the header of an
 * instance's page (its name as typed, no id yet) and Create at its right, faded until the agent is
 * named. The form is kept for a return to the page (`usePageDraft`); once created, the agent's page
 * opens.
 */
import { useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAgentsStore, type Agent } from '@/stores/agents';
import { usePageDraft } from '@/hooks/use-page-state';
import { Button } from '@/components/ui/button';
import { Input, Textarea } from '@/components/ui/input';
import { InstanceHeader } from '@/components/access/instance-header';
import { FormSaveButton, InstanceBack, UnsavedBar } from '@/components/settings/instance-form';
import { SettingsField, SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { AGENT_ICONS, AGENT_ICON_OPTIONS } from '../agent-icons';

const NEW_AGENT = {
  name: '',
  description: '',
  icon: 'sparkles' as Agent['icon'],
  systemPrompt: 'You are a helpful AI assistant.',
};

export default function NewAgentPage() {
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const { addAgent } = useAgentsStore();
  const server = useMemo(() => ({ ...NEW_AGENT }), []);
  const draft = usePageDraft(workspaceId ? { scope: `workspace:${workspaceId}`, page: 'agents', detail: 'new' } : null, server);
  const values = draft.values ?? server;
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list = `/workspace/${workspaceId}/settings/agents`;

  const create = async () => {
    if (!values.name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const id = await addAgent({
        name: values.name.trim(),
        description: values.description.trim(),
        icon: values.icon as Agent['icon'],
        systemPrompt: values.systemPrompt,
        providerId: null,
        provider: null,
        modelId: null,
        logoUrl: null,
        tools: ['search_knowledge', 'search_files', 'read_ontology'],
        capabilities: { memory: true, reasoning: false, vision: false },
        intentMappings: [],
      });
      draft.discard();
      router.push(`${list}/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the agent.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <InstanceBack href={list} label="agents" />
      <InstanceHeader
        name={values.name.trim() || 'New agent'}
        id={null}
        meta={<span>An agent this workspace builds: a model and a prompt.</span>}
        actions={
          <FormSaveButton
            dirty={!!values.name.trim()}
            saving={creating}
            onSave={() => void create()}
            label="Create agent"
            action="create"
          />
        }
      />
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}
      <UnsavedBar show={draft.dirty.length > 0} onDiscard={draft.discard} disabled={creating} />

      <SettingsSection>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <SettingsField label="Name *">
              <Input
                type="text"
                aria-label="Name"
                value={values.name}
                onChange={(e) => draft.set({ name: e.target.value })}
                placeholder="Agent name"
                autoFocus
              />
            </SettingsField>
            <SettingsField label="Icon">
              <div className="flex gap-2">
                {AGENT_ICON_OPTIONS.map((icon) => {
                  const IconComp = AGENT_ICONS[icon];
                  return (
                    <Button
                      key={icon}
                      variant="secondary"
                      size="icon"
                      aria-label={icon}
                      onClick={() => draft.set({ icon })}
                      className={cn(
                        'h-9 w-9',
                        values.icon === icon && 'border-primary bg-primary/10 text-primary hover:bg-primary/10'
                      )}
                    >
                      <IconComp size={16} />
                    </Button>
                  );
                })}
              </div>
            </SettingsField>
          </div>
          <SettingsField label="Description">
            <Input
              type="text"
              aria-label="Description"
              value={values.description}
              onChange={(e) => draft.set({ description: e.target.value })}
              placeholder="Brief description"
            />
          </SettingsField>
          <SettingsField label="System Prompt">
            <Textarea
              aria-label="System Prompt"
              value={values.systemPrompt}
              onChange={(e) => draft.set({ systemPrompt: e.target.value })}
              placeholder="You are a helpful AI assistant..."
              rows={6}
              className="resize-y"
            />
          </SettingsField>
        </div>
      </SettingsSection>
    </div>
  );
}
