import { describe, expect, it } from 'vitest';
import { describeTaskEvent, TASK_EVENT_GROUPS, type TaskEventNames } from './task-events';
import { TASK_ACTIVITY_FIELDS, type TaskActivity } from './tasks';

const names: TaskEventNames = {
  member: (id) => ({ 'u-1': 'Ada', 'u-2': 'Grace', 'u-3': 'Linus' })[id] ?? 'Former member',
  iteration: (id) => (id ? 'Oct 19 – Oct 25' : 'Backlog'),
  stage: (key) => ({ ready: 'Ready', review: 'Review' })[key] ?? key,
  priority: (key) => ({ high: 'High' })[key] ?? key,
};

const event = (field: string, old_value: unknown = null, new_value: unknown = null): TaskActivity => ({
  id: 'e',
  task_id: 't',
  task_title: 'Spec',
  actor_id: 'u-1',
  field,
  old_value,
  new_value,
  created_at: '2026-10-24T09:00:00',
});

const feed = (e: TaskActivity) => describeTaskEvent(e, names, { withTask: true });

describe('task event summaries', () => {
  it('names the task in the feed and says "it" on the task itself', () => {
    expect(feed(event('stage', 'ready', 'review'))).toBe('moved “Spec” from Ready to Review');
    expect(describeTaskEvent(event('stage', 'ready', 'review'), names)).toBe('moved it from Ready to Review');
  });

  it('says who was assigned and unassigned', () => {
    expect(feed(event('assignees', ['u-1'], ['u-2', 'u-3']))).toBe(
      'assigned Grace and Linus to “Spec” and unassigned Ada from “Spec”',
    );
  });

  it('describes field changes', () => {
    expect(feed(event('created'))).toBe('created “Spec”');
    expect(feed(event('title', 'Draft', 'Spec'))).toBe('renamed “Draft” to “Spec”');
    expect(feed(event('content'))).toBe('edited the description of “Spec”');
    expect(feed(event('priority', null, 'high'))).toBe('set the priority on “Spec” to High');
    expect(feed(event('priority', 'high', null))).toBe('removed the priority on “Spec”');
    expect(feed(event('due_date', null, null))).toBe('cleared the due date on “Spec”');
    expect(feed(event('labels', ['Bug'], ['Data']))).toBe('added label Data and removed label Bug on “Spec”');
    expect(feed(event('iteration', 'i-1', null))).toBe('moved “Spec” to the backlog');
    expect(feed(event('archived', false, true))).toBe('archived “Spec”');
    expect(feed(event('deleted'))).toBe('deleted “Spec”');
    expect(feed(event('github_issue', null, 'https://github.com/acme/abi/issues/42'))).toBe(
      'linked “Spec” to GitHub issue acme/abi#42',
    );
    expect(feed(event('github_issue', 'https://github.com/acme/abi/issues/42', null))).toBe(
      'unlinked GitHub issue acme/abi#42 from “Spec”',
    );
  });

  it('quotes comments and names whose comment it was', () => {
    expect(feed(event('comment_added', null, 'Looks good'))).toBe('commented on “Spec”: “Looks good”');
    expect(feed(event('comment_replied', 'u-2', 'Agreed'))).toBe('replied to Grace on “Spec”: “Agreed”');
    expect(feed(event('comment_removed', 'Oops', 'u-1'))).toBe('removed their comment on “Spec”');
    expect(feed(event('comment_removed', 'Spam', 'u-2'))).toBe('removed Grace’s comment on “Spec”');
  });

  it('lists every event kind once in the settings groups', () => {
    expect(TASK_EVENT_GROUPS.flatMap((g) => g.fields).sort()).toEqual([...TASK_ACTIVITY_FIELDS].sort());
  });
});
