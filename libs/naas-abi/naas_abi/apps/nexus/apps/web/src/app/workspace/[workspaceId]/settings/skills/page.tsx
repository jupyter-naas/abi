'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Trash2, XCircle, Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Select, Textarea } from '@/components/ui/input';
import { SettingsPageHeader, SettingsTableToolbar, countLabel } from '@/components/settings/settings-ui';
import { Field } from '@/components/ui/field';
import { Notice } from '@/components/ui/notice';
import { Card } from '@/components/ui/card';
import {
  SettingsTableClear,
  SettingsTableHead,
  SettingsTableNoMatch,
  useSettingsTable,
} from '@/components/settings/users-table/settings-table';
import { TablePager } from '@/components/settings/users-table/table-pager';
import { UsersExportMenu } from '@/components/settings/users-table/users-table-actions';
import { downloadTableExport, type UsersExportFormat } from '@/components/settings/users-table/users-table-export';
import { useSkillsStore, type SkillScope } from '@/stores/skills';
import { useAuthStore } from '@/stores/auth';
import {
  SCOPE_LABELS,
  SKILL_COLUMNS,
  SKILL_EXPORT_HEADERS,
  lastUsedDay,
  skillCellValues,
  skillExportRow,
  skillSearchTexts,
  skillSortValue,
} from './skills-model';

export default function SkillsSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;

  const { skillsByWorkspace, fetchSkills, createSkill, updateSkill, deleteSkill } =
    useSkillsStore();
  const currentUserId = useAuthStore((s) => s.user?.id);

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

  const table = useSettingsTable({
    rows: skills,
    columns: SKILL_COLUMNS,
    cellValues: skillCellValues,
    searchTexts: skillSearchTexts,
    sortValue: skillSortValue,
    initialSort: 'skill',
  });
  const enabledCount = skills.filter((s) => s.enabled).length;

  const exportShown = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(SKILL_EXPORT_HEADERS, table.shown.map(skillExportRow), format, `skills_${date}`, 'Skills');
  };

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
            Reusable prompts, run in the chat with /&lt;slug&gt;; /create-skill writes one for you
          </>
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Add Skill
            </Button>
          </>
        }
      />

      {showAddForm && (
        <Card title="Add New Skill">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Name *">
                <Input
                  type="text"
                  value={newSkill.name}
                  onChange={(e) => setNewSkill({ ...newSkill, name: e.target.value })}
                  placeholder="Weekly report"
                />
              </Field>
              <Field label="Slug">
                <Input
                  type="text"
                  value={newSkill.slug}
                  onChange={(e) => setNewSkill({ ...newSkill, slug: e.target.value })}
                  placeholder="weekly-report (defaults from name)"
                  className="font-mono"
                />
              </Field>
            </div>
            <Field label="Description">
              <Input
                type="text"
                value={newSkill.description}
                onChange={(e) => setNewSkill({ ...newSkill, description: e.target.value })}
                placeholder="One sentence describing what this skill does"
              />
            </Field>
            <Field label="Prompt *">
              <Textarea
                value={newSkill.prompt}
                onChange={(e) => setNewSkill({ ...newSkill, prompt: e.target.value })}
                placeholder="The reusable prompt the agent will apply when this skill is invoked"
                rows={5}
              />
            </Field>
            <Field label="Visibility">
              <Select
                value={newSkill.scope}
                onChange={(e) => setNewSkill({ ...newSkill, scope: e.target.value as SkillScope })}
                className="w-auto"
              >
                <option value="user">Private (only me)</option>
                <option value="workspace">Workspace</option>
                <option value="organization">Organization</option>
              </Select>
            </Field>
            {formError && <Notice tone="error">{formError}</Notice>}
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
        </Card>
      )}

      {actionError && (
        <Notice tone="error" icon={<XCircle size={14} />}>
          {actionError}
        </Notice>
      )}

      <SettingsTableToolbar
        search={table.search}
        onSearchChange={table.setSearch}
        searchPlaceholder="Search skills..."
        meta={
          <>
            {`${countLabel(table.shown.length, skills.length, 'skill')} · ${enabledCount} enabled`}
            <SettingsTableClear table={table} />
          </>
        }
      />

      <div className="org-settings-users-table-wrap">
        <table className="org-settings-users-table">
          <SettingsTableHead table={table} trailing={<th aria-label="Actions" className="w-24" />} />
          <tbody>
            {skills.length === 0 ? (
              <tr>
                <td colSpan={SKILL_COLUMNS.length + 1} className="org-settings-users-no-match">
                  No skills yet. Type /create-skill in the chat, or add one here.
                </td>
              </tr>
            ) : (
              table.shown.length === 0 && <SettingsTableNoMatch colSpan={SKILL_COLUMNS.length + 1} noun="skills" />
            )}
            {table.paged.pageRows.map((skill) => {
              const canModify = skill.scope !== 'user' || skill.userId === currentUserId;
              return (
                <tr
                  key={skill.id}
                  data-skill={skill.slug}
                  onClick={() => router.push(`/workspace/${workspaceId}/settings/skills/${skill.id}`)}
                  className="cursor-pointer"
                >
                  <td>
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
                  <td className="font-mono text-primary">/{skill.slug}</td>
                  <td>
                    <Badge variant="outline">{SCOPE_LABELS[skill.scope]}</Badge>
                  </td>
                  <td className="text-muted-foreground">{lastUsedDay(skill) || '—'}</td>
                  <td data-field="enabled" onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={skill.enabled}
                      onCheckedChange={(checked) => handleToggleEnabled(skill.id, checked)}
                      disabled={!canModify}
                      aria-label={skill.enabled ? 'Disable' : 'Enable'}
                      title={skill.enabled ? 'Disable' : 'Enable'}
                    />
                  </td>
                  <td className="whitespace-nowrap text-right" onClick={(e) => e.stopPropagation()}>
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
            })}
          </tbody>
        </table>
      </div>
      <TablePager total={table.shown.length} paged={table.paged} />
      {confirmDialog}
    </div>
  );
}
