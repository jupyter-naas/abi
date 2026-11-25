'use client';

import { useState } from 'react';
import {
  CalendarDays,
  CircleDot,
  Flag,
  Github,
  Plus,
  Repeat,
  Tag,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react';
import { Popover } from '@/components/database-view/primitives';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import type { TaskFields, TaskIteration, TasksMember, TasksSettings } from '@/lib/tasks';
import { Avatars } from './task-card';
import { MarkdownEditor } from './markdown-editor';
import { GithubIssueInput, isGithubIssueUrl } from './github-issue-input';
import { ChipEditor } from './task-drawer';

/** Iteration choice standing for the open tab's own iteration, created on save if needed. */
const SCOPE_ITERATION = '__scope__';
const FORM_ID = 'tasks-new-task-form';

function PropLabel({ icon: Icon, htmlFor, children }: { icon: LucideIcon; htmlFor?: string; children: string }) {
  const Element = htmlFor ? 'label' : 'span';
  return (
    <Element className="tasks-drawer-label tasks-create-prop-label" htmlFor={htmlFor}>
      <Icon size={13} aria-hidden />
      {children}
    </Element>
  );
}

export interface TaskCreateDefaults {
  stage: string;
  /** null for the backlog; undefined for the open tab's iteration. */
  iterationId?: string | null;
}

export function TaskCreateDialog({
  defaults,
  scopeIterationLabel,
  iterations,
  iterationLabel,
  members,
  memberName,
  labels,
  settings,
  onCreate,
  onClose,
}: {
  defaults: TaskCreateDefaults;
  /** Name of the open tab's iteration, when the tab has one. */
  scopeIterationLabel: string | null;
  iterations: TaskIteration[];
  iterationLabel: (iterationId: string) => string;
  members: TasksMember[];
  memberName: (userId: string) => string;
  labels: string[];
  settings: Pick<TasksSettings, 'stages' | 'priorities' | 'suggested_labels'>;
  onCreate: (fields: TaskFields & { title: string }) => Promise<unknown>;
  onClose: () => void;
}) {
  const [title, setTitle] = useState('');
  const [stage, setStage] = useState(defaults.stage);
  const [iteration, setIteration] = useState(
    defaults.iterationId === undefined ? SCOPE_ITERATION : defaults.iterationId ?? '',
  );
  const [assignees, setAssignees] = useState<string[]>([]);
  const [priority, setPriority] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [taskLabels, setTaskLabels] = useState<string[]>([]);
  const [content, setContent] = useState('');
  const [githubIssue, setGithubIssue] = useState('');
  const [saving, setSaving] = useState(false);

  const toggleAssignee = (userId: string) =>
    setAssignees((prev) => (prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]));

  const submit = async () => {
    const value = title.trim();
    if (!value || saving || !isGithubIssueUrl(githubIssue)) return;
    setSaving(true);
    try {
      await onCreate({
        title: value,
        stage,
        ...(iteration === SCOPE_ITERATION ? {} : { iteration_id: iteration || null }),
        assignee_ids: assignees,
        priority: priority || null,
        due_date: dueDate || null,
        labels: taskLabels,
        github_issue_url: githubIssue.trim(),
        content,
      });
      onClose();
    } catch {
      // Shown in the page's error banner; the form keeps what was typed.
      setSaving(false);
    }
  };

  return (
    <Dialog
      size="lg"
      aria-label="New task"
      className="tasks-dialog"
      title={
        <input
          data-autofocus
          form={FORM_ID}
          className="tasks-drawer-title w-full"
          value={title}
          maxLength={300}
          aria-label="Title"
          placeholder="Task title"
          onChange={(e) => setTitle(e.target.value)}
        />
      }
      onClose={onClose}
      onSubmit={() => void submit()}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={FORM_ID} disabled={saving || !title.trim() || !isGithubIssueUrl(githubIssue)}>
            Create task
          </Button>
        </>
      }
    >
      <form
        id={FORM_ID}
        className="tasks-dialog-form"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        {/* Every property a person sets; workspace and audit fields are set by the server. */}
        <div className="tasks-drawer-fields tasks-create-props">
          <PropLabel icon={CircleDot} htmlFor="tasks-new-stage">Stage</PropLabel>
          <select
            id="tasks-new-stage"
            className="tasks-drawer-select"
            value={stage}
            onChange={(e) => setStage(e.target.value)}
          >
            {settings.stages.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>

          <PropLabel icon={Users}>Assignees</PropLabel>
          <div className="tasks-drawer-chips">
            {assignees.map((id) => (
              <span key={id} className="tasks-drawer-chip">
                <Avatars names={[memberName(id)]} />
                {memberName(id)}
                <button
                  type="button"
                  className="tasks-drawer-chip-remove"
                  title={`Unassign ${memberName(id)}`}
                  onClick={() => toggleAssignee(id)}
                >
                  <X size={11} />
                </button>
              </span>
            ))}
            <Popover
              width="w-72"
              trigger={({ toggle }) => (
                <button type="button" className="tasks-column-add tasks-column-add-inline" onClick={toggle}>
                  <Plus size={12} /> Assign
                </button>
              )}
            >
              <div className="space-y-0.5">
                {members.length === 0 && (
                  <p className="px-2 py-1 text-xs text-muted-foreground">No workspace members found.</p>
                )}
                {members.map((member) => (
                  <button
                    key={member.user_id}
                    type="button"
                    className="tasks-drawer-member-option"
                    onClick={() => toggleAssignee(member.user_id)}
                  >
                    <input type="checkbox" readOnly checked={assignees.includes(member.user_id)} tabIndex={-1} />
                    <span className="truncate">{member.name || member.email}</span>
                    {member.name && member.email && (
                      <span className="tasks-drawer-member-email truncate">{member.email}</span>
                    )}
                  </button>
                ))}
              </div>
            </Popover>
          </div>

          <PropLabel icon={Flag} htmlFor="tasks-new-priority">Priority</PropLabel>
          <select
            id="tasks-new-priority"
            className="tasks-drawer-select"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          >
            <option value="">No priority</option>
            {settings.priorities.map((p) => (
              <option key={p.key} value={p.key}>{p.label}</option>
            ))}
          </select>

          <PropLabel icon={Tag}>Labels</PropLabel>
          <ChipEditor
            values={taskLabels}
            suggestions={Array.from(new Set([...settings.suggested_labels, ...labels]))}
            placeholder="Add a label"
            onChange={setTaskLabels}
          />

          <PropLabel icon={CalendarDays} htmlFor="tasks-new-due">Due date</PropLabel>
          <input
            id="tasks-new-due"
            type="date"
            className="tasks-drawer-input"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />

          <PropLabel icon={Github} htmlFor="tasks-new-github">GitHub issue</PropLabel>
          <GithubIssueInput id="tasks-new-github" value={githubIssue} onChange={setGithubIssue} />

          <PropLabel icon={Repeat} htmlFor="tasks-new-iteration">Iteration</PropLabel>
          <select
            id="tasks-new-iteration"
            className="tasks-drawer-select"
            value={iteration}
            onChange={(e) => setIteration(e.target.value)}
          >
            <option value="">Backlog</option>
            {scopeIterationLabel && <option value={SCOPE_ITERATION}>{scopeIterationLabel}</option>}
            {[...iterations].reverse().map((it) => (
              <option key={it.id} value={it.id}>
                {iterationLabel(it.id)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <p className="tasks-drawer-section-title">Content</p>
          <MarkdownEditor
            value={content}
            maxLength={20000}
            ariaLabel="Content"
            placeholder="Context, acceptance criteria, links… Markdown supported."
            onChange={setContent}
          />
        </div>
      </form>
    </Dialog>
  );
}
