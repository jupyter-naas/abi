'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Search, X, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSkillsStore, type SkillScope } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';

const SCOPE_LABELS: Record<SkillScope, string> = {
  user: 'Private',
  workspace: 'Workspace',
  organization: 'Organization',
};

export default function SkillsSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;

  const { skillsByWorkspace, fetchSkills, createSkill, updateSkill, deleteSkill } =
    useSkillsStore();
  const currentUserId = useAuthStore((s) => s.user?.id);

  const [searchQuery, setSearchQuery] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [newSkill, setNewSkill] = useState({
    name: '',
    slug: '',
    description: '',
    prompt: '',
    scope: 'user' as SkillScope,
  });

  useEffect(() => {
    if (workspaceId) void fetchSkills(workspaceId, true);
  }, [workspaceId, fetchSkills]);

  const skills = useMemo(
    () => skillsByWorkspace[workspaceId] ?? [],
    [skillsByWorkspace, workspaceId]
  );

  const filteredSkills = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return skills;
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.slug.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
    );
  }, [skills, searchQuery]);

  const handleAddSkill = async () => {
    if (!newSkill.name.trim() || !newSkill.prompt.trim()) {
      setFormError('Name and prompt are required');
      return;
    }
    setFormError(null);
    try {
      await createSkill(workspaceId, {
        name: newSkill.name.trim(),
        slug: newSkill.slug.trim() || undefined,
        description: newSkill.description.trim() || undefined,
        prompt: newSkill.prompt,
        scope: newSkill.scope,
      });
      setNewSkill({ name: '', slug: '', description: '', prompt: '', scope: 'user' });
      setShowAddForm(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create skill');
    }
  };

  const handleToggleEnabled = async (id: string, enabled: boolean) => {
    try {
      await updateSkill(id, { enabled });
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to update skill');
    }
  };

  const handleDelete = async (id: string, slug: string) => {
    if (!confirm(`Delete skill "/${slug}"?`)) return;
    try {
      await deleteSkill(id);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete skill');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Skills</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {filteredSkills.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Reusable prompts invocable in the chat with /&lt;slug&gt; — or type /create-skill in
            the chat to let the agent draft one
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus size={16} />
          Add Skill
        </button>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <h3 className="mb-4 font-medium">Add New Skill</h3>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Name *</label>
                <input
                  type="text"
                  value={newSkill.name}
                  onChange={(e) => setNewSkill({ ...newSkill, name: e.target.value })}
                  placeholder="Weekly report"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Slug</label>
                <input
                  type="text"
                  value={newSkill.slug}
                  onChange={(e) => setNewSkill({ ...newSkill, slug: e.target.value })}
                  placeholder="weekly-report (defaults from name)"
                  className="w-full rounded-lg border bg-background px-3 py-2 font-mono text-sm outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input
                type="text"
                value={newSkill.description}
                onChange={(e) => setNewSkill({ ...newSkill, description: e.target.value })}
                placeholder="One sentence describing what this skill does"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Prompt *</label>
              <textarea
                value={newSkill.prompt}
                onChange={(e) => setNewSkill({ ...newSkill, prompt: e.target.value })}
                placeholder="The reusable prompt the agent will apply when this skill is invoked"
                rows={5}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Visibility</label>
              <select
                value={newSkill.scope}
                onChange={(e) => setNewSkill({ ...newSkill, scope: e.target.value as SkillScope })}
                className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="user">Private (only me)</option>
                <option value="workspace">Workspace</option>
                <option value="organization">Organization</option>
              </select>
            </div>
            {formError && <p className="text-sm text-destructive">{formError}</p>}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setFormError(null);
                }}
                className="rounded-lg border px-3 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleAddSkill}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Add Skill
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      {skills.length > 0 && (
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <input
            type="text"
            placeholder="Search skills..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border bg-background py-2 pl-10 pr-10 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X size={16} />
            </button>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-sm">
              <th className="p-3 font-medium">Skill</th>
              <th className="p-3 font-medium">Command</th>
              <th className="p-3 font-medium">Visibility</th>
              <th className="p-3 font-medium">Last used</th>
              <th className="w-24 p-3 font-medium">Enabled</th>
              <th className="w-24 p-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSkills.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  {searchQuery
                    ? `No skills match "${searchQuery}"`
                    : 'No skills yet. Type /create-skill in the chat or add one here.'}
                </td>
              </tr>
            ) : (
              filteredSkills.map((skill) => {
                const canModify = skill.scope !== 'user' || skill.userId === currentUserId;
                return (
                  <tr
                    key={skill.id}
                    onClick={() =>
                      router.push(`/workspace/${workspaceId}/settings/skills/${skill.id}`)
                    }
                    className="cursor-pointer border-b transition-colors hover:bg-muted/30"
                  >
                    <td className="p-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                          <Zap size={16} className="text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium">{skill.name}</p>
                          {skill.description && (
                            <p className="truncate text-xs text-muted-foreground">
                              {skill.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="p-3 font-mono text-sm text-workspace-accent">/{skill.slug}</td>
                    <td className="p-3 text-sm">{SCOPE_LABELS[skill.scope]}</td>
                    <td className="p-3 text-sm text-muted-foreground">
                      {skill.lastUsedAt ? new Date(skill.lastUsedAt).toLocaleDateString() : '—'}
                    </td>
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleToggleEnabled(skill.id, !skill.enabled)}
                        disabled={!canModify}
                        className={cn(
                          'relative h-5 w-9 rounded-full transition-colors disabled:opacity-50',
                          skill.enabled ? 'bg-primary' : 'bg-muted-foreground/30'
                        )}
                        title={skill.enabled ? 'Disable' : 'Enable'}
                      >
                        <span
                          className={cn(
                            'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all',
                            skill.enabled ? 'left-[18px]' : 'left-0.5'
                          )}
                        />
                      </button>
                    </td>
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      {canModify && (
                        <button
                          onClick={() => handleDelete(skill.id, skill.slug)}
                          className="rounded-md px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
