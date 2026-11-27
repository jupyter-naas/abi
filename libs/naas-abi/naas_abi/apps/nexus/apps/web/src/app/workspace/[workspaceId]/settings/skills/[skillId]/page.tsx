'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Select, Textarea } from '@/components/ui/input';
import { usePageDraft } from '@/hooks/use-page-state';
import { InstanceHeader } from '@/components/access/instance-header';
import { FormSaveButton, InstanceBack, UnsavedBar } from '@/components/settings/instance-form';
import { SettingsField, SettingsLoading, SettingsNotice, SettingsSection } from '@/components/settings/settings-ui';
import { useSkillsStore, type SkillScope } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';
import { SCOPE_LABELS } from '../skills-model';

const FIELD_LABELS: Record<string, string> = {
  name: 'Name',
  slug: 'Slug',
  description: 'Description',
  prompt: 'Prompt',
  scope: 'Visibility',
  enabled: 'Enabled',
};

/**
 * A skill's page under Workspace settings › Skills: the header of an instance's page (its name, its
 * /slug and id), Save at its right, faded until something changes, the unsaved bar; the edits are
 * kept for a return to the page (`usePageDraft`).
 */
export default function SkillEditorPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const skillId = params.skillId as string;

  const { skillsByWorkspace, fetchSkills, updateSkill } = useSkillsStore();
  const currentUserId = useAuthStore((s) => s.user?.id);

  const skill = useMemo(
    () => (skillsByWorkspace[workspaceId] ?? []).find((s) => s.id === skillId),
    [skillsByWorkspace, workspaceId, skillId]
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (workspaceId) void fetchSkills(workspaceId, true);
  }, [workspaceId, fetchSkills]);

  // The skill as the store holds it, and the edits over it.
  const server = useMemo(
    () =>
      skill
        ? {
            name: skill.name,
            slug: skill.slug,
            description: skill.description ?? '',
            prompt: skill.prompt,
            scope: skill.scope as string,
            enabled: skill.enabled,
          }
        : null,
    [skill]
  );
  const draft = usePageDraft(
    workspaceId && skillId ? { scope: `workspace:${workspaceId}`, page: 'skills', detail: skillId } : null,
    server
  );
  const values = draft.values ?? server;
  const dirty =
    !!server && !!values && (Object.keys(server) as (keyof typeof server)[]).some((key) => server[key] !== values[key]);
  const set = (changes: Partial<NonNullable<typeof server>>) => {
    setSaved(false);
    draft.set(changes);
  };

  const canModify = skill ? skill.scope !== 'user' || skill.userId === currentUserId : false;

  const handleSave = async () => {
    if (!skill || !values) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateSkill(skill.id, {
        name: values.name.trim(),
        slug: values.slug.trim(),
        description: values.description.trim(),
        prompt: values.prompt,
        scope: values.scope as SkillScope,
        enabled: values.enabled,
      });
      draft.discard();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save skill');
    } finally {
      setSaving(false);
    }
  };

  if (!skill || !values) {
    return <SettingsLoading label="Loading skill…" />;
  }

  return (
    <div className="space-y-6">
      <InstanceBack href={`/workspace/${workspaceId}/settings/skills`} label="skills" />
      <InstanceHeader
        name={skill.name}
        id={skill.id}
        slug={skill.slug}
        meta={<span>{SCOPE_LABELS[skill.scope]}</span>}
        actions={
          <FormSaveButton dirty={dirty} saving={saving} saved={saved} onSave={() => void handleSave()} disabled={!canModify} />
        }
      />

      {!canModify && <SettingsNotice>Only the creator can modify this private skill.</SettingsNotice>}
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}
      <UnsavedBar
        show={dirty}
        conflicts={draft.conflicts.map((field) => FIELD_LABELS[field] ?? field)}
        onDiscard={draft.discard}
        disabled={saving}
      />

      <SettingsSection>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <SettingsField label="Name">
              <Input
                type="text"
                aria-label="Name"
                value={values.name}
                onChange={(e) => set({ name: e.target.value })}
                disabled={!canModify}
              />
            </SettingsField>
            <SettingsField label="Slug">
              <Input
                type="text"
                aria-label="Slug"
                value={values.slug}
                onChange={(e) => set({ slug: e.target.value })}
                disabled={!canModify}
                className="font-mono"
              />
            </SettingsField>
          </div>
          <SettingsField label="Description">
            <Input
              type="text"
              aria-label="Description"
              value={values.description}
              onChange={(e) => set({ description: e.target.value })}
              disabled={!canModify}
            />
          </SettingsField>
          <SettingsField label="Prompt">
            <Textarea
              aria-label="Prompt"
              value={values.prompt}
              onChange={(e) => set({ prompt: e.target.value })}
              disabled={!canModify}
              rows={12}
            />
          </SettingsField>
          <div className="flex items-end gap-6">
            <SettingsField label="Visibility">
              <Select
                aria-label="Visibility"
                value={values.scope}
                onChange={(e) => set({ scope: e.target.value })}
                disabled={!canModify}
                className="w-auto"
              >
                <option value="user">Private (only me)</option>
                <option value="workspace">Workspace</option>
                <option value="organization">Organization</option>
              </Select>
            </SettingsField>
            <Checkbox
              checked={values.enabled}
              onCheckedChange={(checked) => set({ enabled: checked })}
              disabled={!canModify}
              label="Enabled"
              className="h-9"
            />
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}
