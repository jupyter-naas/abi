'use client';

import { useEffect, useMemo, useState } from 'react';
import { BulkBar, SelectAllCell, SelectRowCell, onOffActions, useRowSelection } from '@/components/settings/bulk-access';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Trash2, XCircle, Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Select, Textarea } from '@/components/ui/input';
import {
  SettingsField,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
  SettingsTableToolbar,
} from '@/components/settings/settings-ui';
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

/** The batch actions: enable or disable the skills selected. */
const BULK_ACTIONS = onOffActions({ on: 'Enable', off: 'Disable' });

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
  const [notice, setNotice] = useState('');
  const [switching, setSwitching] = useState(false);
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

  // A table of switches: each change saved at once, and said.
  const handleToggleEnabled = async (id: string, enabled: boolean) => {
    setActionError(null);
    setNotice('');
    try {
      await updateSkill(id, { enabled });
      const skill = skills.find((s) => s.id === id);
      setNotice(`/${skill?.slug ?? id} ${enabled ? 'enabled' : 'disabled'}.`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update skill');
    }
  };

  // The skills checked for a batch change (the rows shown: select all takes them).
  const selection = useRowSelection(useMemo(() => table.shown.map((skill) => skill.id), [table.shown]));
  const canModifySkill = (skill: (typeof skills)[number]) => skill.scope !== 'user' || skill.userId === currentUserId;
  /** Enable or disable every selected skill the caller may change, one after the other. */
  const applyBulk = async (id: string) => {
    const enabled = id === 'on';
    const picked = skills.filter((s) => selection.selected.has(s.id) && canModifySkill(s) && s.enabled !== enabled);
    setActionError(null);
    setNotice('');
    setSwitching(true);
    let done = 0;
    try {
      for (const skill of picked) {
        await updateSkill(skill.id, { enabled });
        done += 1;
      }
      setNotice(`${done} skill${done === 1 ? '' : 's'} ${enabled ? 'enabled' : 'disabled'}.`);
    } catch (err) {
      setActionError(
        `${err instanceof Error ? err.message : 'Failed to update skill'} (${done} of ${picked.length} changed)`
      );
    } finally {
      setSwitching(false);
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
        // One total: how many skills (the Enabled column says which are on).
        badge={`${skills.length} skill${skills.length === 1 ? '' : 's'}`}
        description={
          <>
            Reusable prompts invocable in the chat with /&lt;slug&gt; — or type /create-skill in the chat and the
            Skills agent writes and saves one for you
          </>
        }
        actions={
          <>
            <UsersExportMenu onExport={exportShown} disabled={table.shown.length === 0} />
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Create skill
            </Button>
          </>
        }
      />

      {showAddForm && (
        <SettingsSection title="Create skill">
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
              <Button onClick={handleAddSkill}>Create</Button>
            </div>
          </div>
        </SettingsSection>
      )}

      {actionError && (
        <SettingsNotice tone="error" icon={<XCircle size={14} />}>
          {actionError}
        </SettingsNotice>
      )}
      {notice && (
        <p className="text-xs text-muted-foreground" role="status" data-skills-notice="">
          {notice}
        </p>
      )}

      <SettingsTableToolbar
        search={table.search}
        onSearchChange={table.setSearch}
        searchPlaceholder="Search skills..."
        // No count above the search: the badge says how many, the pager how many are shown.
        meta={<SettingsTableClear table={table} />}
      />
      <BulkBar
        selection={selection}
        noun="skill"
        actions={BULK_ACTIONS}
        onApply={applyBulk}
        skippedFor={() => skills.filter((s) => selection.selected.has(s.id) && !canModifySkill(s)).length}
        change="this change"
        disabled={switching}
      />

      <div className="org-settings-users-table-wrap">
        <table className="org-settings-users-table">
          <SettingsTableHead
            table={table}
            leading={
              <SelectAllCell
                selection={selection}
                keys={table.shown.filter(canModifySkill).map((skill) => skill.id)}
                noun="skill"
                disabled={switching}
              />
            }
            trailing={<th aria-label="Actions" className="w-24" />}
          />
          <tbody>
            {skills.length === 0 ? (
              <tr>
                <td colSpan={SKILL_COLUMNS.length + 2} className="org-settings-users-no-match">
                  No skills yet. Type /create-skill in the chat, or create one here.
                </td>
              </tr>
            ) : (
              table.shown.length === 0 && <SettingsTableNoMatch colSpan={SKILL_COLUMNS.length + 2} noun="skills" />
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
                  <SelectRowCell
                    selection={selection}
                    rowKey={skill.id}
                    label={skill.name}
                    disabled={switching || !canModify}
                  />
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
