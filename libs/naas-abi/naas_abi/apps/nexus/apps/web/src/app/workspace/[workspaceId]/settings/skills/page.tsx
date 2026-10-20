'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Trash2, XCircle, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Select, Textarea } from '@/components/ui/input';
import {
  SettingsField,
  SettingsNotice,
  SettingsPageHeader,
  SettingsFilterSelect,
  SettingsSection,
  SettingsTableToolbar,
  countLabel,
  settingsTable,
} from '@/components/settings/settings-ui';
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
  const [scopeFilter, setScopeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();
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
    return skills.filter((s) => {
      if (scopeFilter !== 'all' && s.scope !== scopeFilter) return false;
      if (statusFilter === 'enabled' && !s.enabled) return false;
      if (statusFilter === 'disabled' && s.enabled) return false;
      return (
        !q ||
        s.name.toLowerCase().includes(q) ||
        s.slug.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
      );
    });
  }, [skills, searchQuery, scopeFilter, statusFilter]);
  const enabledCount = skills.filter((s) => s.enabled).length;

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
    setActionError(null);
    try {
      await updateSkill(id, { enabled });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update skill');
    }
  };

  const handleDelete = async (id: string, slug: string) => {
    const ok = await confirmDelete({ title: `Delete skill "/${slug}"?`, confirmLabel: 'Delete' });
    if (!ok) return;
    setActionError(null);
    try {
      await deleteSkill(id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete skill');
    }
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Skills"
        badge={`${enabledCount} enabled`}
        description={
          <>
            Reusable prompts invocable in the chat with /&lt;slug&gt; — or type /create-skill in the chat and the
            Skills agent writes and saves one for you
          </>
        }
        actions={
          <Button onClick={() => setShowAddForm(true)}>
            <Plus size={16} />
            Add Skill
          </Button>
        }
      />

      {showAddForm && (
        <SettingsSection title="Add New Skill">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <SettingsField label="Name *">
                <Input
                  type="text"
                  value={newSkill.name}
                  onChange={(e) => setNewSkill({ ...newSkill, name: e.target.value })}
                  placeholder="Weekly report"
                />
              </SettingsField>
              <SettingsField label="Slug">
                <Input
                  type="text"
                  value={newSkill.slug}
                  onChange={(e) => setNewSkill({ ...newSkill, slug: e.target.value })}
                  placeholder="weekly-report (defaults from name)"
                  className="font-mono"
                />
              </SettingsField>
            </div>
            <SettingsField label="Description">
              <Input
                type="text"
                value={newSkill.description}
                onChange={(e) => setNewSkill({ ...newSkill, description: e.target.value })}
                placeholder="One sentence describing what this skill does"
              />
            </SettingsField>
            <SettingsField label="Prompt *">
              <Textarea
                value={newSkill.prompt}
                onChange={(e) => setNewSkill({ ...newSkill, prompt: e.target.value })}
                placeholder="The reusable prompt the agent will apply when this skill is invoked"
                rows={5}
              />
            </SettingsField>
            <SettingsField label="Visibility">
              <Select
                value={newSkill.scope}
                onChange={(e) => setNewSkill({ ...newSkill, scope: e.target.value as SkillScope })}
                className="w-auto"
              >
                <option value="user">Private (only me)</option>
                <option value="workspace">Workspace</option>
                <option value="organization">Organization</option>
              </Select>
            </SettingsField>
            {formError && <SettingsNotice tone="error">{formError}</SettingsNotice>}
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowAddForm(false);
                  setFormError(null);
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleAddSkill}>Add Skill</Button>
            </div>
          </div>
        </SettingsSection>
      )}

      {actionError && (
        <SettingsNotice tone="error" icon={<XCircle size={14} />}>
          {actionError}
        </SettingsNotice>
      )}

      <SettingsTableToolbar
        search={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Search skills..."
        filters={
          <>
            <SettingsFilterSelect
              label="Visibility"
              value={scopeFilter}
              onChange={setScopeFilter}
              options={[
                { value: 'all', label: 'All visibilities' },
                ...(Object.keys(SCOPE_LABELS) as SkillScope[]).map((scope) => ({
                  value: scope,
                  label: SCOPE_LABELS[scope],
                })),
              ]}
            />
            <SettingsFilterSelect
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: 'All statuses' },
                { value: 'enabled', label: 'Enabled' },
                { value: 'disabled', label: 'Disabled' },
              ]}
            />
          </>
        }
        meta={`${countLabel(filteredSkills.length, skills.length, 'skill')} · ${enabledCount} enabled`}
      />

      <div className={settingsTable.wrapper}>
        <table className={settingsTable.table}>
          <thead>
            <tr className={settingsTable.headRow}>
              <th className={settingsTable.th}>Skill</th>
              <th className={settingsTable.th}>Command</th>
              <th className={settingsTable.th}>Visibility</th>
              <th className={settingsTable.th}>Last used</th>
              <th className={cn(settingsTable.th, 'w-24')}>Enabled</th>
              <th className={cn(settingsTable.th, 'w-24')}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSkills.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  {skills.length > 0
                    ? 'No skills match the current search and filters'
                    : 'No skills yet. Type /create-skill in the chat, or add one here.'}
                </td>
              </tr>
            ) : (
              filteredSkills.map((skill) => {
                const canModify = skill.scope !== 'user' || skill.userId === currentUserId;
                return (
                  <tr
                    key={skill.id}
                    onClick={() => router.push(`/workspace/${workspaceId}/settings/skills/${skill.id}`)}
                    className={cn(settingsTable.row, 'cursor-pointer')}
                  >
                    <td className={settingsTable.td}>
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center bg-muted">
                          <Zap size={16} className="text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium">{skill.name}</p>
                          {skill.description && (
                            <p className="truncate text-xs text-muted-foreground">{skill.description}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className={cn(settingsTable.td, 'font-mono text-primary')}>/{skill.slug}</td>
                    <td className={settingsTable.td}>
                      <Badge variant="outline">{SCOPE_LABELS[skill.scope]}</Badge>
                    </td>
                    <td className={cn(settingsTable.td, 'text-muted-foreground')}>
                      {skill.lastUsedAt ? new Date(skill.lastUsedAt).toLocaleDateString() : '—'}
                    </td>
                    <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={skill.enabled}
                        onCheckedChange={(checked) => handleToggleEnabled(skill.id, checked)}
                        disabled={!canModify}
                        aria-label={skill.enabled ? 'Disable' : 'Enable'}
                        title={skill.enabled ? 'Disable' : 'Enable'}
                      />
                    </td>
                    <td className={settingsTable.td} onClick={(e) => e.stopPropagation()}>
                      {canModify && (
                        <Button
                          variant="destructive-ghost"
                          size="icon"
                          onClick={() => handleDelete(skill.id, skill.slug)}
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {confirmDialog}
    </div>
  );
}
