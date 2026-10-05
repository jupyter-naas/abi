'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useSkillsStore, type Skill, type SkillScope } from '@/stores/skills';
import {
  SKILL_MD_PATH,
  addSkillDraftFile,
  initialSkillDraftFiles,
  removeSkillDraftFile,
  skillDraftBody,
  updateSkillDraftFile,
  type SkillDraftFile,
} from '../skill-draft-files';
import { SkillRecordView } from '../skill-record-view';

const INSTRUCTIONS_PLACEHOLDER =
  'Summarize recent work in three sections: wins, blockers, and next steps.';

function suggestedSlug(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/_/g, '-')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  if (!slug || slug === 'skills' || slug === 'create-skill') return '';
  return slug;
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
  } catch {
    // The response was not JSON.
  }
  return fallback;
}

export default function NewSkillPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;
  const { createSkill, updateSkill, fetchSkills } = useSkillsStore();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [scope, setScope] = useState<SkillScope>('user');
  const [enabled, setEnabled] = useState(true);
  const [files, setFiles] = useState<SkillDraftFile[]>(initialSkillDraftFiles);
  const [pickedPath, setPickedPath] = useState(SKILL_MD_PATH);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedSkill, setSavedSkill] = useState<Skill | null>(null);

  const selectedPath = files.some((file) => file.path === pickedPath) ? pickedPath : SKILL_MD_PATH;
  const selected = files.find((file) => file.path === selectedPath) ?? files[0];
  const skillBody = skillDraftBody(files, SKILL_MD_PATH);
  const preview = suggestedSlug(name);
  const editingExtra = selectedPath !== SKILL_MD_PATH;
  const listHref = `/workspace/${workspaceId}/settings/skills`;

  const setSkillBody = (body: string) => {
    setFiles((current) => updateSkillDraftFile(current, SKILL_MD_PATH, body));
  };

  const handleAddFile = (rawPath: string): string | null => {
    try {
      const next = addSkillDraftFile(files, rawPath);
      setFiles(next);
      setPickedPath(next[next.length - 1]?.path ?? SKILL_MD_PATH);
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : 'Could not add that file.';
    }
  };

  const handleRemoveFile = (path: string) => {
    setFiles((current) => removeSkillDraftFile(current, path));
    if (pickedPath === path) setPickedPath(SKILL_MD_PATH);
  };

  const handleCreate = async () => {
    const trimmedName = name.trim();
    const trimmedDescription = description.trim();
    if (!trimmedName || !skillBody.trim()) {
      setError('Name and instructions are required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      let skill = savedSkill;
      if (!skill) {
        skill = await createSkill(workspaceId, {
          name: trimmedName,
          description: trimmedDescription || undefined,
          prompt: skillBody,
          scope,
          enabled,
        });
      } else {
        skill = await updateSkill(skill.id, {
          name: trimmedName,
          description: trimmedDescription,
          prompt: skillBody,
          scope,
          enabled,
        });
      }
      setSavedSkill(skill);

      const { authFetch } = await import('@/stores/auth');
      const { getApiUrl } = await import('@/lib/config');
      const response = await authFetch(`${getApiUrl()}/api/skills/package`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          slug: skill.slug,
          name: trimmedName,
          description: trimmedDescription || trimmedName,
          when_to_use: trimmedDescription || 'The user invokes this skill.',
          body: skillBody,
          files: files
            .filter((file) => file.path !== SKILL_MD_PATH)
            .map((file) => ({ path: file.path, body: file.body })),
        }),
      });
      if (!response.ok) {
        const detail = await readError(response, 'Could not write the skill files.');
        setError(`The skill was saved, but its files were not written. ${detail}`);
        setSaving(false);
        return;
      }
      await fetchSkills(workspaceId, true);
      router.push(`/workspace/${workspaceId}/settings/skills/${skill.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create skill');
      setSaving(false);
    }
  };

  return (
    <SkillRecordView
      title={name.trim() || 'New skill'}
      subtitle={
        preview ? <span className="font-mono text-primary">/{preview}</span> : 'A new skill in this workspace.'
      }
      onBack={() => router.push(listHref)}
      actions={
        <>
          <Button variant="secondary" onClick={() => router.push(listHref)} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={() => void handleCreate()} disabled={saving}>
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saving ? 'Creating' : 'Create'}
          </Button>
        </>
      }
      canModify
      error={error}
      name={name}
      onNameChange={setName}
      slug={preview}
      slugReadOnly
      slugHint="The slash command is created from the name."
      description={description}
      onDescriptionChange={setDescription}
      scope={scope}
      onScopeChange={setScope}
      enabled={enabled}
      onEnabledChange={setEnabled}
      files={files.map((file) => file.path)}
      selectedPath={selected.path}
      selectedText={editingExtra ? null : skillBody}
      onSelectFile={setPickedPath}
      fileEditor={{
        value: editingExtra ? selected.body : skillBody,
        onChange: (body) =>
          setFiles((current) =>
            updateSkillDraftFile(current, editingExtra ? selected.path : SKILL_MD_PATH, body),
          ),
        placeholder: editingExtra ? undefined : INSTRUCTIONS_PLACEHOLDER,
      }}
      onAddFile={handleAddFile}
      onRemoveFile={handleRemoveFile}
      prompt={skillBody}
      onPromptChange={setSkillBody}
      promptPlaceholder={INSTRUCTIONS_PLACEHOLDER}
    />
  );
}
