'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { canModifySkill, useSkillsStore, type SkillScope } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';
import { SkillRecordView } from '../skill-record-view';

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
  const [pickedFile, setPickedFile] = useState<string | null>(null);
  const [selectedFileText, setSelectedFileText] = useState<string | null>(null);

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

  const canModify = skill ? canModifySkill(skill, currentUserId) : false;
  const packageFiles = skill?.files ?? [];
  const selectedFile =
    pickedFile && packageFiles.includes(pickedFile)
      ? pickedFile
      : packageFiles.includes('SKILL.md')
        ? 'SKILL.md'
        : (packageFiles[0] ?? null);

  useEffect(() => {
    if (!skill || !selectedFile) {
      setSelectedFileText(null);
      return;
    }
    let cancelled = false;
    setSelectedFileText(null);
    void (async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        const { getApiUrl } = await import('@/lib/config');
        const response = await authFetch(
          `${getApiUrl()}/api/skills/${encodeURIComponent(skill.id)}/files/${selectedFile
            .split('/')
            .map(encodeURIComponent)
            .join('/')}`,
        );
        if (!response.ok) {
          if (!cancelled) setSelectedFileText('Could not read this file.');
          return;
        }
        const payload = (await response.json()) as { content?: string };
        if (!cancelled) setSelectedFileText(payload.content ?? '');
      } catch {
        if (!cancelled) setSelectedFileText(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [skill, selectedFile]);

  // Module catalog rows disclose metadata; load instructions only on this detail page.
  useEffect(() => {
    if (skill?.source !== 'module') return;
    let cancelled = false;
    void (async () => {
      const { authFetch } = await import('@/stores/auth');
      const { getApiUrl } = await import('@/lib/config');
      try {
        const response = await authFetch(`${getApiUrl()}/api/skills/${encodeURIComponent(skill.id)}`);
        if (!response.ok) throw new Error('Could not load skill instructions.');
        const loaded = await response.json();
        if (!cancelled) setPrompt(loaded.prompt ?? '');
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load skill instructions.');
      }
    })();
    return () => { cancelled = true; };
  }, [skill?.id, skill?.source]);

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
    <SkillRecordView
      title={skill.name}
      subtitle={<span className="font-mono text-primary">/{skill.slug}{skill.catalogRef ? ` · ${skill.catalogRef}` : ''}</span>}
      onBack={() => router.push(`/workspace/${workspaceId}/settings/skills`)}
      actions={
        <Button onClick={handleSave} disabled={saving || !canModify}>
          {saving && <Loader2 size={14} className="animate-spin" />}
          {saved ? 'Saved' : 'Save'}
        </Button>
      }
      builtin={skill.builtin}
      builtinSlug={skill.slug}
      canModify={canModify}
      error={error}
      name={name}
      onNameChange={setName}
      slug={slug}
      onSlugChange={setSlug}
      description={description}
      onDescriptionChange={setDescription}
      scope={scope}
      onScopeChange={setScope}
      enabled={enabled}
      onEnabledChange={setEnabled}
      files={packageFiles}
      selectedPath={selectedFile}
      selectedText={selectedFileText}
      onSelectFile={(path) => {
        setPickedFile(path);
        setSelectedFileText(null);
      }}
      prompt={prompt}
      onPromptChange={setPrompt}
    />
  );
}
