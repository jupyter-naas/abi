'use client';

/**
 * Workspace settings › Skills › Create skill: a page, as Create workspace is, with the header of an
 * instance's page and Create at its right, faded until the skill has a name and a prompt. The form is
 * kept for a return to the page (`usePageDraft`); once created, the skill's page opens.
 */
import { useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSkillsStore, type SkillScope } from '@/stores/skills';
import { usePageDraft } from '@/hooks/use-page-state';
import { Input, Select, Textarea } from '@/components/ui/input';
import { InstanceHeader } from '@/components/access/instance-header';
import { FormSaveButton, InstanceBack, UnsavedBar } from '@/components/settings/instance-form';
import { SettingsField, SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { usePolicyHref } from '@/components/settings/use-policy-href';

const NEW_SKILL: { name: string; slug: string; description: string; prompt: string; scope: string } = {
  name: '',
  slug: '',
  description: '',
  prompt: '',
  scope: 'user',
};

export default function NewSkillPage() {
  // Links keep the policy picked in the Settings column (`?policy=`).
  const policyHref = usePolicyHref();
  const workspaceId = useParams().workspaceId as string;
  const router = useRouter();
  const { createSkill } = useSkillsStore();
  const server = useMemo(() => ({ ...NEW_SKILL }), []);
  const draft = usePageDraft(workspaceId ? { scope: `workspace:${workspaceId}`, page: 'skills', detail: 'new' } : null, server);
  const values = draft.values ?? server;
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list = `/workspace/${workspaceId}/settings/skills`;
  const ready = !!values.name.trim() && !!values.prompt.trim();

  const create = async () => {
    if (!ready) return;
    setCreating(true);
    setError(null);
    try {
      const skill = await createSkill(workspaceId, {
        name: values.name.trim(),
        slug: values.slug.trim() || undefined,
        description: values.description.trim() || undefined,
        prompt: values.prompt,
        scope: values.scope as SkillScope,
      });
      draft.discard();
      router.push(policyHref(`${list}/${skill.id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the skill.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <InstanceBack href={list} label="skills" />
      <InstanceHeader
        name={values.name.trim() || 'New skill'}
        id={null}
        slug={values.slug.trim() || null}
        meta={<span>A reusable prompt, run in the chat with /&lt;slug&gt;.</span>}
        actions={
          <FormSaveButton dirty={ready} saving={creating} onSave={() => void create()} label="Create skill" action="create" />
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
                placeholder="Weekly report"
                autoFocus
              />
            </SettingsField>
            <SettingsField label="Slug">
              <Input
                type="text"
                aria-label="Slug"
                value={values.slug}
                onChange={(e) => draft.set({ slug: e.target.value })}
                placeholder="weekly-report (defaults from name)"
                className="font-mono"
              />
            </SettingsField>
          </div>
          <SettingsField label="Description">
            <Input
              type="text"
              aria-label="Description"
              value={values.description}
              onChange={(e) => draft.set({ description: e.target.value })}
              placeholder="One sentence describing what this skill does"
            />
          </SettingsField>
          <SettingsField label="Prompt *">
            <Textarea
              aria-label="Prompt"
              value={values.prompt}
              onChange={(e) => draft.set({ prompt: e.target.value })}
              placeholder="The reusable prompt the agent will apply when this skill is invoked"
              rows={8}
            />
          </SettingsField>
          <SettingsField label="Visibility">
            <Select
              aria-label="Visibility"
              value={values.scope}
              onChange={(e) => draft.set({ scope: e.target.value })}
              className="w-auto"
            >
              <option value="user">Private (only me)</option>
              <option value="workspace">Workspace</option>
              <option value="organization">Organization</option>
            </Select>
          </SettingsField>
        </div>
      </SettingsSection>
    </div>
  );
}
