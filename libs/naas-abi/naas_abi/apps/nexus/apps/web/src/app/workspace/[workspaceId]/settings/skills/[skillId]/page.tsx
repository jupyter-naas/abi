'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input, Select, Textarea } from '@/components/ui/input';
import {
  SettingsField,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
} from '@/components/settings/settings-ui';
import { useSkillsStore, type SkillScope } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';

export default function SkillEditorPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const skillId = params.skillId as string;

  const { skillsByWorkspace, fetchSkills, updateSkill } = useSkillsStore();
  const currentUserId = useAuthStore((s) => s.user?.id);

  const skill = useMemo(
    () => (skillsByWorkspace[workspaceId] ?? []).find((s) => s.id === skillId),
    [skillsByWorkspace, workspaceId, skillId]
  );

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [prompt, setPrompt] = useState('');
  const [scope, setScope] = useState<SkillScope>('user');
  const [enabled, setEnabled] = useState(true);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (workspaceId) void fetchSkills(workspaceId, true);
  }, [workspaceId, fetchSkills]);

  // Seed the form once per skill load.
  useEffect(() => {
    if (skill && loadedId !== skill.id) {
      setName(skill.name);
      setSlug(skill.slug);
      setDescription(skill.description);
      setPrompt(skill.prompt);
      setScope(skill.scope);
      setEnabled(skill.enabled);
      setLoadedId(skill.id);
    }
  }, [skill, loadedId]);

  const canModify = skill ? skill.scope !== 'user' || skill.userId === currentUserId : false;

  const handleSave = async () => {
    if (!skill) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await updateSkill(skill.id, {
        name: name.trim(),
        slug: slug.trim(),
        description: description.trim(),
        prompt,
        scope,
        enabled,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save skill');
    } finally {
      setSaving(false);
    }
  };

  if (!skill) {
    return <SettingsLoading label="Loading skill…" />;
  }

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        leading={
          <Button
            variant="secondary"
            size="icon"
            className="h-9 w-9"
            onClick={() => router.push(`/workspace/${workspaceId}/settings/skills`)}
            title="Back to skills"
          >
            <ArrowLeft size={16} />
          </Button>
        }
        title={skill.name}
        description={<span className="font-mono text-primary">/{skill.slug}</span>}
        actions={
          <Button onClick={handleSave} disabled={saving || !canModify}>
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saved ? 'Saved' : 'Save'}
          </Button>
        }
      />

      {!canModify && <SettingsNotice>Only the creator can modify this private skill.</SettingsNotice>}
      {error && <SettingsNotice tone="error">{error}</SettingsNotice>}

      <SettingsSection>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <SettingsField label="Name">
              <Input type="text" value={name} onChange={(e) => setName(e.target.value)} disabled={!canModify} />
            </SettingsField>
            <SettingsField label="Slug">
              <Input
                type="text"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                disabled={!canModify}
                className="font-mono"
              />
            </SettingsField>
          </div>
          <SettingsField label="Description">
            <Input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={!canModify}
            />
          </SettingsField>
          <SettingsField label="Prompt">
            <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} disabled={!canModify} rows={12} />
          </SettingsField>
          <div className="flex items-end gap-6">
            <SettingsField label="Visibility">
              <Select
                value={scope}
                onChange={(e) => setScope(e.target.value as SkillScope)}
                disabled={!canModify}
                className="w-auto"
              >
                <option value="user">Private (only me)</option>
                <option value="workspace">Workspace</option>
                <option value="organization">Organization</option>
              </Select>
            </SettingsField>
            <Checkbox
              checked={enabled}
              onCheckedChange={setEnabled}
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
