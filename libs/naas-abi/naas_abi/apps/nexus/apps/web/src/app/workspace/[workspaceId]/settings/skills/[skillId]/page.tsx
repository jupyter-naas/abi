'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Loader2 } from 'lucide-react';
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
    return (
      <div className="flex items-center gap-2 p-8 text-muted-foreground">
        <Loader2 size={16} className="animate-spin" />
        Loading skill...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/workspace/${workspaceId}/settings/skills`)}
            className="rounded-lg border p-2 hover:bg-muted"
            title="Back to skills"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h2 className="text-lg font-semibold">{skill.name}</h2>
            <p className="font-mono text-sm text-workspace-accent">/{skill.slug}</p>
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !canModify}
          className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          {saved ? 'Saved' : 'Save'}
        </button>
      </div>

      {!canModify && (
        <p className="rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
          Only the creator can modify this private skill.
        </p>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="grid gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!canModify}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Slug</label>
            <input
              type="text"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={!canModify}
              className="w-full rounded-lg border bg-background px-3 py-2 font-mono text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Description</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={!canModify}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Prompt</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={!canModify}
            rows={12}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
          />
        </div>
        <div className="flex items-center gap-6">
          <div>
            <label className="mb-1 block text-sm font-medium">Visibility</label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as SkillScope)}
              disabled={!canModify}
              className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
            >
              <option value="user">Private (only me)</option>
              <option value="workspace">Workspace</option>
              <option value="organization">Organization</option>
            </select>
          </div>
          <label className="flex items-center gap-2 pt-5 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              disabled={!canModify}
            />
            Enabled
          </label>
        </div>
      </div>
    </div>
  );
}
