'use client';

import { useCallback, useEffect, useState } from 'react';
import { Archive, ArchiveRestore, Plus, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Popover } from '@/components/database-view/primitives';
import {
  boardApi,
  choiceLabel,
  type BoardActivity,
  type BoardComment,
  type BoardIteration,
  type BoardMember,
  type BoardSettings,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';
import { formatDate } from '../lib/task-schema';
import { Avatars } from './task-card';

function formatTimestamp(value: string | null): string {
  if (!value) return '';
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

export function describeActivity(
  entry: BoardActivity,
  names: {
    member: (id: string) => string;
    iteration: (id: string | null) => string;
    stage: (key: string) => string;
  },
): string {
  switch (entry.field) {
    case 'created':
      return 'created the task';
    case 'stage':
      return `moved it from ${names.stage(String(entry.old_value))} to ${names.stage(String(entry.new_value))}`;
    case 'assignees': {
      const before = asList(entry.old_value);
      const after = asList(entry.new_value);
      const added = after.filter((id) => !before.includes(id)).map(names.member);
      const removed = before.filter((id) => !after.includes(id)).map(names.member);
      const parts = [
        added.length ? `assigned ${added.join(', ')}` : '',
        removed.length ? `unassigned ${removed.join(', ')}` : '',
      ].filter(Boolean);
      return parts.join(' and ') || 'changed the assignees';
    }
    case 'iteration':
      return `moved it from ${names.iteration(entry.old_value as string | null)} to ${names.iteration(
        entry.new_value as string | null,
      )}`;
    case 'archived':
      return entry.new_value ? 'archived the task' : 'restored the task';
    default:
      return `changed ${entry.field}`;
  }
}

function ChipEditor({
  values,
  suggestions,
  placeholder,
  onChange,
}: {
  values: string[];
  suggestions: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState('');
  const listId = `board-chips-${placeholder.replace(/\W+/g, '-').toLowerCase()}`;
  const add = () => {
    const value = draft.trim();
    setDraft('');
    if (value && !values.includes(value)) onChange([...values, value]);
  };
  return (
    <div className="board-drawer-chips">
      {values.map((value) => (
        <span key={value} className="board-drawer-chip">
          {value}
          <button
            type="button"
            className="board-drawer-chip-remove"
            title={`Remove ${value}`}
            onClick={() => onChange(values.filter((v) => v !== value))}
          >
            <X size={11} />
          </button>
        </span>
      ))}
      <input
        className="board-drawer-chip-input"
        list={listId}
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            add();
          }
          if (e.key === 'Backspace' && !draft && values.length) onChange(values.slice(0, -1));
        }}
        onBlur={add}
      />
      <datalist id={listId}>
        {suggestions.filter((s) => !values.includes(s)).map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
    </div>
  );
}

export function TaskDrawer({
  workspaceId,
  task,
  iterations,
  iterationLabel,
  members,
  memberName,
  projects,
  labels,
  settings,
  onUpdate,
  onArchive,
  onDelete,
  onClose,
}: {
  workspaceId: string;
  task: BoardTask;
  iterations: BoardIteration[];
  iterationLabel: (iterationId: string) => string;
  members: BoardMember[];
  memberName: (userId: string) => string;
  /** Projects and labels already used on the board, offered as suggestions. */
  projects: string[];
  labels: string[];
  /** Stages, priorities and suggested labels. */
  settings: Pick<BoardSettings, 'stages' | 'priorities' | 'suggested_labels'>;
  onUpdate: (fields: TaskFields) => Promise<unknown>;
  onArchive: (archived: boolean) => Promise<unknown>;
  onDelete: () => Promise<unknown>;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(task.title);
  const [content, setContent] = useState(task.content);
  const [project, setProject] = useState(task.project);
  const [tab, setTab] = useState<'comments' | 'activity'>('comments');
  const [comments, setComments] = useState<BoardComment[]>([]);
  const [activity, setActivity] = useState<BoardActivity[]>([]);
  const [commentDraft, setCommentDraft] = useState('');
  const [posting, setPosting] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);

  // Another task opened, or this one changed elsewhere: take the server values.
  useEffect(() => {
    setTitle(task.title);
    setContent(task.content);
    setProject(task.project);
  }, [task.id, task.title, task.content, task.project]);

  const loadFeed = useCallback(async () => {
    try {
      const [c, a] = await Promise.all([
        boardApi.listComments(workspaceId, task.id),
        boardApi.listActivity(workspaceId, task.id),
      ]);
      setComments(c);
      setActivity(a);
      setFeedError(null);
    } catch (e) {
      setFeedError((e as Error).message);
    }
  }, [workspaceId, task.id]);

  // Reload after every change of the task, so its own edits show in Activity.
  useEffect(() => {
    void loadFeed();
  }, [loadFeed, task.updated_at]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const save = (fields: TaskFields) => {
    void onUpdate(fields).catch(() => undefined);
  };

  const commitTitle = () => {
    const next = title.trim();
    if (!next) setTitle(task.title);
    else if (next !== task.title) save({ title: next });
  };

  const toggleAssignee = (userId: string) => {
    const next = task.assignee_ids.includes(userId)
      ? task.assignee_ids.filter((id) => id !== userId)
      : [...task.assignee_ids, userId];
    save({ assignee_ids: next });
  };

  const postComment = async () => {
    const body = commentDraft.trim();
    if (!body) return;
    setPosting(true);
    try {
      const created = await boardApi.addComment(workspaceId, task.id, body);
      setComments((prev) => [...prev, created]);
      setCommentDraft('');
      setFeedError(null);
    } catch (e) {
      setFeedError((e as Error).message);
    } finally {
      setPosting(false);
    }
  };

  const iterationName = (id: string | null) => (id ? iterationLabel(id) : 'Backlog');

  return (
    <>
      <div className="board-drawer-backdrop" onClick={onClose} />
      <aside className="board-drawer" role="dialog" aria-label={`Task ${task.title}`}>
        <header className="board-drawer-header">
          <input
            className="board-drawer-title"
            value={title}
            maxLength={300}
            aria-label="Title"
            onChange={(e) => setTitle(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
          />
          <button type="button" className="board-icon-button" title="Close" onClick={onClose}>
            <X size={14} />
          </button>
        </header>

        <div className="board-drawer-body">
          <div className="board-drawer-fields">
            <label className="board-drawer-label" htmlFor="board-task-stage">Stage</label>
            <select
              id="board-task-stage"
              className="board-drawer-select"
              value={task.stage}
              onChange={(e) => save({ stage: e.target.value })}
            >
              {settings.stages.map((stage) => (
                <option key={stage.key} value={stage.key}>{stage.label}</option>
              ))}
              {!settings.stages.some((s) => s.key === task.stage) && <option value={task.stage}>{task.stage}</option>}
            </select>

            <span className="board-drawer-label">Assignees</span>
            <div className="board-drawer-chips">
              {task.assignee_ids.map((id) => (
                <span key={id} className="board-drawer-chip">
                  <Avatars names={[memberName(id)]} />
                  {memberName(id)}
                  <button
                    type="button"
                    className="board-drawer-chip-remove"
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
                  <button type="button" className="board-column-add board-column-add-inline" onClick={toggle}>
                    <Plus size={12} /> Assign
                  </button>
                )}
              >
                <div className="space-y-0.5">
                  {members.length === 0 && (
                    <p className="px-2 py-1 text-xs text-muted-foreground">No workspace members found.</p>
                  )}
                  {members.map((member) => {
                    const assigned = task.assignee_ids.includes(member.user_id);
                    return (
                      <button
                        key={member.user_id}
                        type="button"
                        className="board-drawer-member-option"
                        onClick={() => toggleAssignee(member.user_id)}
                      >
                        <input type="checkbox" readOnly checked={assigned} tabIndex={-1} />
                        <span className="truncate">{member.name || member.email}</span>
                        {member.name && member.email && (
                          <span className="board-drawer-member-email truncate">{member.email}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </Popover>
            </div>

            <label className="board-drawer-label" htmlFor="board-task-iteration">Iteration</label>
            <select
              id="board-task-iteration"
              className="board-drawer-select"
              value={task.iteration_id ?? ''}
              onChange={(e) => save({ iteration_id: e.target.value || null })}
            >
              <option value="">Backlog</option>
              {[...iterations].reverse().map((iteration) => (
                <option key={iteration.id} value={iteration.id}>
                  {iterationLabel(iteration.id)}
                </option>
              ))}
            </select>

            <label className="board-drawer-label" htmlFor="board-task-project">Project</label>
            <input
              id="board-task-project"
              className="board-drawer-input"
              list="board-task-projects"
              value={project}
              maxLength={120}
              placeholder="No project"
              onChange={(e) => setProject(e.target.value)}
              onBlur={() => project.trim() !== task.project && save({ project: project.trim() })}
              onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
            />
            <datalist id="board-task-projects">
              {projects.map((p) => <option key={p} value={p} />)}
            </datalist>

            <label className="board-drawer-label" htmlFor="board-task-priority">Priority</label>
            <select
              id="board-task-priority"
              className="board-drawer-select"
              value={task.priority ?? ''}
              onChange={(e) => save({ priority: e.target.value || null })}
            >
              <option value="">No priority</option>
              {settings.priorities.map((priority) => (
                <option key={priority.key} value={priority.key}>{priority.label}</option>
              ))}
            </select>

            <label className="board-drawer-label" htmlFor="board-task-due">Due date</label>
            <input
              id="board-task-due"
              type="date"
              className="board-drawer-input"
              value={task.due_date ?? ''}
              onChange={(e) => save({ due_date: e.target.value || null })}
            />

            <span className="board-drawer-label">Labels</span>
            <ChipEditor
              values={task.labels}
              suggestions={Array.from(new Set([...settings.suggested_labels, ...labels]))}
              placeholder="Add a label"
              onChange={(next) => save({ labels: next })}
            />
          </div>

          <div>
            <p className="board-drawer-section-title">Content</p>
            <textarea
              className="board-drawer-textarea"
              value={content}
              maxLength={20000}
              placeholder="Context, acceptance criteria, links…"
              onChange={(e) => setContent(e.target.value)}
              onBlur={() => content !== task.content && save({ content })}
            />
          </div>

          <div className="board-drawer-audit">
            <span>Created by {task.created_by ? memberName(task.created_by) : '—'}</span>
            <span>{formatTimestamp(task.created_at)}</span>
            <span>Last updated by {task.updated_by ? memberName(task.updated_by) : '—'}</span>
            <span>{formatTimestamp(task.updated_at)}</span>
            {task.archived && <span>Archived {formatDate(task.archived_at)}</span>}
          </div>

          <div>
            <div className="board-drawer-tabs">
              {(['comments', 'activity'] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  className={cn('board-drawer-tab', tab === key && 'board-drawer-tab-active')}
                  onClick={() => setTab(key)}
                >
                  {key === 'comments' ? `Comments (${comments.length})` : 'Activity'}
                </button>
              ))}
            </div>
            {feedError && <p className="board-task-card-overdue mt-2 text-xs">{feedError}</p>}
            {tab === 'comments' ? (
              <div className="mt-3 space-y-3">
                <ul className="board-drawer-feed">
                  {comments.length === 0 && <li className="board-drawer-feed-meta">No comments yet.</li>}
                  {comments.map((comment) => (
                    <li key={comment.id} className="board-drawer-feed-item">
                      <span className="board-drawer-feed-meta">
                        {comment.author_id ? memberName(comment.author_id) : 'Former member'} ·{' '}
                        {formatTimestamp(comment.created_at)}
                      </span>
                      <p className="board-drawer-comment-body">{comment.body}</p>
                    </li>
                  ))}
                </ul>
                <div className="board-drawer-comment-form">
                  <textarea
                    className="board-drawer-textarea"
                    value={commentDraft}
                    maxLength={5000}
                    placeholder="Write a comment…"
                    onChange={(e) => setCommentDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void postComment();
                    }}
                  />
                  <button
                    type="button"
                    className="board-button board-button-primary"
                    disabled={posting || !commentDraft.trim()}
                    onClick={() => void postComment()}
                  >
                    Comment
                  </button>
                </div>
              </div>
            ) : (
              <ul className="board-drawer-feed mt-3">
                {activity.map((entry) => (
                  <li key={entry.id} className="board-drawer-feed-item">
                    <strong>{entry.actor_id ? memberName(entry.actor_id) : 'Someone'}</strong>{' '}
                    {describeActivity(entry, {
                      member: memberName,
                      iteration: iterationName,
                      stage: (key) => choiceLabel(settings.stages, key),
                    })}
                    <span className="board-drawer-feed-meta">{formatTimestamp(entry.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <footer className="board-drawer-footer">
          {task.archived ? (
            <button type="button" className="board-button" onClick={() => void onArchive(false).catch(() => undefined)}>
              <ArchiveRestore size={13} /> Restore
            </button>
          ) : (
            <button type="button" className="board-button" onClick={() => void onArchive(true).catch(() => undefined)}>
              <Archive size={13} /> Archive
            </button>
          )}
          <span className="board-drawer-footer-spacer" />
          <button type="button" className="board-button board-button-danger" onClick={() => void onDelete()}>
            <Trash2 size={13} /> Delete
          </button>
        </footer>
      </aside>
    </>
  );
}
