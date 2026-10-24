'use client';

import { useCallback, useEffect, useState } from 'react';
import { Archive, ArchiveRestore, CornerDownRight, Plus, Reply, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Popover } from '@/components/database-view/primitives';
import { describeTaskEvent } from '@/lib/task-events';
import { TASKS_CHANGED_EVENT } from '@/stores/tasks';
import {
  tasksApi,
  choiceLabel,
  SCOPE_LABELS,
  type TaskComment,
  type TaskActivity,
  type TaskIteration,
  type TasksMember,
  type TasksSettings,
  type Task,
  type TaskFields,
} from '@/lib/tasks';
import { formatDate } from '../lib/task-schema';
import { Avatars } from './task-card';
import { MarkdownEditor } from './markdown-editor';
import { GithubIssueInput } from './github-issue-input';

/** Iteration choice standing for a scope whose iteration is created on select. */
const PENDING_SCOPE = 'scope:';

function formatTimestamp(value: string | null): string {
  if (!value) return '';
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`);
  return date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function ChipEditor({
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
  const listId = `tasks-chips-${placeholder.replace(/\W+/g, '-').toLowerCase()}`;
  const add = () => {
    const value = draft.trim();
    setDraft('');
    if (value && !values.includes(value)) onChange([...values, value]);
  };
  return (
    <div className="tasks-drawer-chips">
      {values.map((value) => (
        <span key={value} className="tasks-drawer-chip">
          {value}
          <button
            type="button"
            className="tasks-drawer-chip-remove"
            title={`Remove ${value}`}
            onClick={() => onChange(values.filter((v) => v !== value))}
          >
            <X size={11} />
          </button>
        </span>
      ))}
      <input
        className="tasks-drawer-chip-input"
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
  pendingScopes = [],
  resolveScopeIteration,
  members,
  memberName,
  workspaceName,
  labels,
  settings,
  onUpdate,
  onArchive,
  onDelete,
  onClose,
  currentUserId,
  canModerate,
  confirmRemoveComment,
  onFeedChange,
}: {
  workspaceId: string;
  task: Task;
  iterations: TaskIteration[];
  iterationLabel: (iterationId: string) => string;
  /** Last / current / next iterations that do not exist yet, still offered as targets. */
  pendingScopes?: readonly ('last' | 'current' | 'next')[];
  /** Creates a pending scope's iteration and returns its id. */
  resolveScopeIteration?: (scope: 'last' | 'current' | 'next') => Promise<string | null>;
  members: TasksMember[];
  memberName: (userId: string) => string;
  /** Display name of the task's workspace (it stores the id). */
  workspaceName: (workspaceId: string) => string;
  /** Labels already used in the workspace's tasks, offered as suggestions. */
  labels: string[];
  /** Stages, priorities and suggested labels. */
  settings: Pick<TasksSettings, 'stages' | 'priorities' | 'suggested_labels'>;
  onUpdate: (fields: TaskFields) => Promise<unknown>;
  onArchive: (archived: boolean) => Promise<unknown>;
  onDelete: () => Promise<unknown>;
  onClose: () => void;
  /** The viewer: they may remove their own comments. */
  currentUserId: string | null;
  /** Owners and admins may remove anyone's comment. */
  canModerate: boolean;
  confirmRemoveComment: (comment: TaskComment) => Promise<boolean>;
  /** A comment was added or removed: the workspace feed has a new event. */
  onFeedChange: () => void;
}) {
  const [title, setTitle] = useState(task.title);
  const [content, setContent] = useState(task.content);
  const [tab, setTab] = useState<'comments' | 'activity'>('comments');
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [activity, setActivity] = useState<TaskActivity[]>([]);
  const [commentDraft, setCommentDraft] = useState('');
  const [githubIssue, setGithubIssue] = useState(task.github_issue_url ?? '');
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [replyDraft, setReplyDraft] = useState('');
  const [posting, setPosting] = useState(false);
  const [feedError, setFeedError] = useState<string | null>(null);

  // Another task opened, or this one changed elsewhere: take the server values.
  useEffect(() => {
    setTitle(task.title);
    setContent(task.content);
    setGithubIssue(task.github_issue_url ?? '');
  }, [task.id, task.title, task.content, task.github_issue_url]);

  const loadFeed = useCallback(async () => {
    try {
      const [c, a] = await Promise.all([
        tasksApi.listComments(workspaceId, task.id),
        tasksApi.listActivity(workspaceId, task.id),
      ]);
      setComments(c);
      setActivity(a);
      setFeedError(null);
    } catch (e) {
      setFeedError((e as Error).message);
    }
  }, [workspaceId, task.id]);

  // Reload after every change of the task, so its own edits show in Activity,
  // and when the Tasks agent in the chat pane commented or changed something.
  useEffect(() => {
    void loadFeed();
  }, [loadFeed, task.updated_at]);
  useEffect(() => {
    const reload = () => void loadFeed();
    window.addEventListener(TASKS_CHANGED_EVENT, reload);
    return () => window.removeEventListener(TASKS_CHANGED_EVENT, reload);
  }, [loadFeed]);

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

  const moveToIteration = async (value: string) => {
    if (!value.startsWith(PENDING_SCOPE)) return save({ iteration_id: value || null });
    const scope = value.slice(PENDING_SCOPE.length) as 'last' | 'current' | 'next';
    const iterationId = await resolveScopeIteration?.(scope).catch(() => null);
    if (iterationId) save({ iteration_id: iterationId });
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

  /** A new comment, or a reply when ``parentId`` is set. */
  const postComment = async (body: string, parentId?: string) => {
    const text = body.trim();
    if (!text) return false;
    setPosting(true);
    try {
      const created = await tasksApi.addComment(workspaceId, task.id, text, parentId);
      setComments((prev) => [...prev, created]);
      setFeedError(null);
      void loadFeed();
      onFeedChange();
      return true;
    } catch (e) {
      setFeedError((e as Error).message);
      return false;
    } finally {
      setPosting(false);
    }
  };

  const removeComment = async (comment: TaskComment) => {
    if (!(await confirmRemoveComment(comment))) return;
    try {
      await tasksApi.deleteComment(workspaceId, task.id, comment.id);
      // Its replies go with it.
      setComments((prev) => prev.filter((c) => c.id !== comment.id && c.parent_id !== comment.id));
      setFeedError(null);
      void loadFeed();
      onFeedChange();
    } catch (e) {
      setFeedError((e as Error).message);
    }
  };

  const threads = comments.filter((c) => !c.parent_id);
  const repliesOf = (id: string) => comments.filter((c) => c.parent_id === id);

  const renderComment = (comment: TaskComment, threadId: string) => (
    <div className="tasks-drawer-comment">
      <span className="tasks-drawer-feed-meta">
        {comment.author_id ? memberName(comment.author_id) : 'Former member'} · {formatTimestamp(comment.created_at)}
      </span>
      <p className="tasks-drawer-comment-body">{comment.body}</p>
      <span className="tasks-drawer-comment-actions">
        <button
          type="button"
          className="tasks-drawer-comment-action"
          onClick={() => {
            setReplyTo(threadId);
            setReplyDraft('');
          }}
        >
          <Reply size={12} /> Reply
        </button>
        {(comment.author_id === currentUserId || canModerate) && (
          <button
            type="button"
            className="tasks-drawer-comment-action"
            onClick={() => void removeComment(comment)}
          >
            <Trash2 size={12} /> Remove
          </button>
        )}
      </span>
    </div>
  );

  const iterationName = (id: string | null) => (id ? iterationLabel(id) : 'Backlog');

  return (
    // Centered on the Tasks page, like the New task form (never over the shell bars).
    <div className="tasks-create-overlay">
      <div className="tasks-create-backdrop" onClick={onClose} />
      <aside className="tasks-create-dialog tasks-task-dialog" role="dialog" aria-modal="true" aria-label={`Task ${task.title}`}>
        <header className="tasks-drawer-header">
          <input
            className="tasks-drawer-title"
            value={title}
            maxLength={300}
            aria-label="Title"
            onChange={(e) => setTitle(e.target.value)}
            onBlur={commitTitle}
            onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
          />
          <button type="button" className="tasks-icon-button" title="Close" onClick={onClose}>
            <X size={14} />
          </button>
        </header>

        <div className="tasks-drawer-body">
          <div className="tasks-drawer-fields">
            <label className="tasks-drawer-label" htmlFor="tasks-task-stage">Stage</label>
            <select
              id="tasks-task-stage"
              className="tasks-drawer-select"
              value={task.stage}
              onChange={(e) => save({ stage: e.target.value })}
            >
              {settings.stages.map((stage) => (
                <option key={stage.key} value={stage.key}>{stage.label}</option>
              ))}
              {!settings.stages.some((s) => s.key === task.stage) && <option value={task.stage}>{task.stage}</option>}
            </select>

            <span className="tasks-drawer-label">Assignees</span>
            <div className="tasks-drawer-chips">
              {task.assignee_ids.map((id) => (
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
                  {members.map((member) => {
                    const assigned = task.assignee_ids.includes(member.user_id);
                    return (
                      <button
                        key={member.user_id}
                        type="button"
                        className="tasks-drawer-member-option"
                        onClick={() => toggleAssignee(member.user_id)}
                      >
                        <input type="checkbox" readOnly checked={assigned} tabIndex={-1} />
                        <span className="truncate">{member.name || member.email}</span>
                        {member.name && member.email && (
                          <span className="tasks-drawer-member-email truncate">{member.email}</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </Popover>
            </div>

            <label className="tasks-drawer-label" htmlFor="tasks-task-iteration">Iteration</label>
            <select
              id="tasks-task-iteration"
              className="tasks-drawer-select"
              value={task.iteration_id ?? ''}
              onChange={(e) => void moveToIteration(e.target.value)}
            >
              <option value="">Backlog</option>
              {pendingScopes.map((scope) => (
                <option key={scope} value={`${PENDING_SCOPE}${scope}`}>
                  {SCOPE_LABELS[scope]}
                </option>
              ))}
              {[...iterations].reverse().map((iteration) => (
                <option key={iteration.id} value={iteration.id}>
                  {iterationLabel(iteration.id)}
                </option>
              ))}
            </select>

            <span className="tasks-drawer-label">Workspace</span>
            <span className="tasks-drawer-readonly" title={task.workspace_id}>{workspaceName(task.workspace_id)}</span>

            <label className="tasks-drawer-label" htmlFor="tasks-task-priority">Priority</label>
            <select
              id="tasks-task-priority"
              className="tasks-drawer-select"
              value={task.priority ?? ''}
              onChange={(e) => save({ priority: e.target.value || null })}
            >
              <option value="">No priority</option>
              {settings.priorities.map((priority) => (
                <option key={priority.key} value={priority.key}>{priority.label}</option>
              ))}
            </select>

            <label className="tasks-drawer-label" htmlFor="tasks-task-due">Due date</label>
            <input
              id="tasks-task-due"
              type="date"
              className="tasks-drawer-input"
              value={task.due_date ?? ''}
              onChange={(e) => save({ due_date: e.target.value || null })}
            />

            <label className="tasks-drawer-label" htmlFor="tasks-task-github">GitHub issue</label>
            <GithubIssueInput
              id="tasks-task-github"
              value={githubIssue}
              onChange={setGithubIssue}
              onCommit={() =>
                githubIssue.trim() !== (task.github_issue_url ?? '') && save({ github_issue_url: githubIssue.trim() })
              }
            />

            <span className="tasks-drawer-label">Labels</span>
            <ChipEditor
              values={task.labels}
              suggestions={Array.from(new Set([...settings.suggested_labels, ...labels]))}
              placeholder="Add a label"
              onChange={(next) => save({ labels: next })}
            />
          </div>

          <div>
            <p className="tasks-drawer-section-title">Content</p>
            <MarkdownEditor
              value={content}
              maxLength={20000}
              ariaLabel="Content"
              placeholder="Context, acceptance criteria, links… Markdown supported."
              onChange={setContent}
              onBlur={() => content !== task.content && save({ content })}
            />
          </div>

          <div className="tasks-drawer-audit">
            <span>Created by {task.created_by ? memberName(task.created_by) : '—'}</span>
            <span>{formatTimestamp(task.created_at)}</span>
            <span>Last updated by {task.updated_by ? memberName(task.updated_by) : '—'}</span>
            <span>{formatTimestamp(task.updated_at)}</span>
            {task.archived && <span>Archived {formatDate(task.archived_at)}</span>}
          </div>

          <div>
            <div className="tasks-drawer-tabs">
              {(['comments', 'activity'] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  className={cn('tasks-drawer-tab', tab === key && 'tasks-drawer-tab-active')}
                  onClick={() => setTab(key)}
                >
                  {key === 'comments' ? `Comments (${comments.length})` : 'Activity'}
                </button>
              ))}
            </div>
            {feedError && <p className="tasks-task-card-overdue mt-2 text-xs">{feedError}</p>}
            {tab === 'comments' ? (
              <div className="mt-3 space-y-3">
                <ul className="tasks-drawer-feed">
                  {threads.length === 0 && <li className="tasks-drawer-feed-meta">No comments yet.</li>}
                  {threads.map((thread) => (
                    <li key={thread.id} className="tasks-drawer-feed-item">
                      {renderComment(thread, thread.id)}
                      {(repliesOf(thread.id).length > 0 || replyTo === thread.id) && (
                        <ul className="tasks-drawer-replies">
                          {repliesOf(thread.id).map((reply) => (
                            <li key={reply.id} className="tasks-drawer-feed-item">
                              {renderComment(reply, thread.id)}
                            </li>
                          ))}
                          {replyTo === thread.id && (
                            <li className="tasks-drawer-comment-form">
                              <textarea
                                autoFocus
                                className="tasks-drawer-textarea"
                                value={replyDraft}
                                maxLength={5000}
                                placeholder="Write a reply…"
                                onChange={(e) => setReplyDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Escape') {
                                    e.stopPropagation();
                                    e.nativeEvent.stopImmediatePropagation();
                                    setReplyTo(null);
                                  }
                                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                    void postComment(replyDraft, thread.id).then((ok) => ok && setReplyTo(null));
                                  }
                                }}
                              />
                              <span className="tasks-drawer-comment-actions">
                                <button type="button" className="tasks-button" onClick={() => setReplyTo(null)}>
                                  Cancel
                                </button>
                                <button
                                  type="button"
                                  className="tasks-button tasks-button-accent"
                                  disabled={posting || !replyDraft.trim()}
                                  onClick={() =>
                                    void postComment(replyDraft, thread.id).then((ok) => ok && setReplyTo(null))
                                  }
                                >
                                  <CornerDownRight size={12} /> Reply
                                </button>
                              </span>
                            </li>
                          )}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="tasks-drawer-comment-form">
                  <textarea
                    className="tasks-drawer-textarea"
                    value={commentDraft}
                    maxLength={5000}
                    placeholder="Write a comment…"
                    onChange={(e) => setCommentDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        void postComment(commentDraft).then((ok) => ok && setCommentDraft(''));
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="tasks-button tasks-button-accent"
                    disabled={posting || !commentDraft.trim()}
                    onClick={() => void postComment(commentDraft).then((ok) => ok && setCommentDraft(''))}
                  >
                    Comment
                  </button>
                </div>
              </div>
            ) : (
              <ul className="tasks-drawer-feed mt-3">
                {activity.map((entry) => (
                  <li key={entry.id} className="tasks-drawer-feed-item">
                    <strong>{entry.actor_id ? memberName(entry.actor_id) : 'Someone'}</strong>{' '}
                    {describeTaskEvent(entry, {
                      member: memberName,
                      iteration: iterationName,
                      stage: (key) => choiceLabel(settings.stages, key),
                      priority: (key) => choiceLabel(settings.priorities, key),
                    })}
                    <span className="tasks-drawer-feed-meta">{formatTimestamp(entry.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <footer className="tasks-drawer-footer">
          {task.archived ? (
            <button type="button" className="tasks-button" onClick={() => void onArchive(false).catch(() => undefined)}>
              <ArchiveRestore size={13} /> Restore
            </button>
          ) : (
            <button type="button" className="tasks-button" onClick={() => void onArchive(true).catch(() => undefined)}>
              <Archive size={13} /> Archive
            </button>
          )}
          <span className="tasks-drawer-footer-spacer" />
          <button type="button" className="tasks-button tasks-button-danger" onClick={() => void onDelete()}>
            <Trash2 size={13} /> Delete
          </button>
        </footer>
      </aside>
    </div>
  );
}
