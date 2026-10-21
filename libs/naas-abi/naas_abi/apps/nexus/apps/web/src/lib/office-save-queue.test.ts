import { describe, expect, it } from 'vitest';

import { createOfficeSaveQueue } from './office-save-queue';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function controlledWriter() {
  const calls: { content: string; done: ReturnType<typeof deferred<string>> }[] = [];
  const write = (content: string) => {
    const done = deferred<string>();
    calls.push({ content, done });
    return done.promise;
  };
  return { calls, write };
}

describe('createOfficeSaveQueue', () => {
  it('keeps edits made during a delayed save dirty', async () => {
    const { calls, write } = controlledWriter();
    const queue = createOfficeSaveQueue(write);
    queue.load('v0');
    queue.edit('v1');
    const first = queue.save();
    await Promise.resolve();
    queue.edit('v2');
    calls[0].done.resolve('sha1');
    await expect(first).resolves.toEqual({ status: 'saved', result: 'sha1', dirty: true });
    expect(queue.isDirty()).toBe(true);
    expect(calls.map((c) => c.content)).toEqual(['v1']);
  });

  it('serializes saves and coalesces triggers into one save of the newest content', async () => {
    const { calls, write } = controlledWriter();
    const queue = createOfficeSaveQueue(write);
    queue.edit('v1');
    const first = queue.save();
    await Promise.resolve();
    queue.edit('v2');
    const second = queue.save();
    queue.edit('v3');
    const third = queue.save();
    expect(second).toBe(third);
    expect(calls).toHaveLength(1);
    expect(queue.isSaving()).toBe(true);

    calls[0].done.resolve('a');
    await first;
    await new Promise((r) => setTimeout(r, 0));
    expect(calls.map((c) => c.content)).toEqual(['v1', 'v3']);
    calls[1].done.resolve('b');
    await expect(third).resolves.toEqual({ status: 'saved', result: 'b', dirty: false });
    expect(queue.isDirty()).toBe(false);
    expect(queue.isSaving()).toBe(false);
  });

  it('never persists an older snapshot after a newer one', async () => {
    const written: string[] = [];
    const queue = createOfficeSaveQueue(async (content) => {
      await new Promise((r) => setTimeout(r, content === 'v1' ? 20 : 1));
      written.push(content);
      return content;
    });
    queue.edit('v1');
    const a = queue.save();
    queue.edit('v2');
    const b = queue.save();
    await Promise.all([a, b]);
    expect(written).toEqual(['v1', 'v2']);
    expect(queue.isDirty()).toBe(false);
  });

  it('preserves the draft on failure and allows a retry', async () => {
    let fail = true;
    const written: string[] = [];
    const queue = createOfficeSaveQueue(async (content) => {
      if (fail) throw new Error('Save failed (503)');
      written.push(content);
      return 'ok';
    });
    queue.edit('draft');
    const failed = await queue.save();
    expect(failed.status).toBe('failed');
    expect(queue.isDirty()).toBe(true);
    fail = false;
    await expect(queue.save()).resolves.toEqual({ status: 'saved', result: 'ok', dirty: false });
    expect(written).toEqual(['draft']);
  });

  it('reports clean when nothing changed since the last load', async () => {
    const { calls, write } = controlledWriter();
    const queue = createOfficeSaveQueue(write);
    queue.load('server');
    await expect(queue.save()).resolves.toEqual({ status: 'clean' });
    expect(calls).toHaveLength(0);
  });

  it('treats completions after dispose as stale (document or deck switched)', async () => {
    const { calls, write } = controlledWriter();
    const queue = createOfficeSaveQueue(write);
    queue.edit('old doc');
    const pending = queue.save();
    await Promise.resolve();
    queue.dispose();
    calls[0].done.resolve('sha');
    await expect(pending).resolves.toEqual({ status: 'stale' });
    await expect(queue.save()).resolves.toEqual({ status: 'stale' });

    const failing = createOfficeSaveQueue(write);
    failing.edit('x');
    const failed = failing.save();
    await Promise.resolve();
    failing.dispose();
    calls[1].done.reject(new Error('boom'));
    await expect(failed).resolves.toEqual({ status: 'stale' });
  });

  it('a load during a save wins over the save acknowledgement', async () => {
    const { calls, write } = controlledWriter();
    const queue = createOfficeSaveQueue(write);
    queue.edit('local');
    const pending = queue.save();
    await Promise.resolve();
    queue.load('server');
    calls[0].done.resolve('sha');
    await expect(pending).resolves.toEqual({ status: 'saved', result: 'sha', dirty: false });
    queue.edit('after');
    expect(queue.isDirty()).toBe(true);
  });

  it('surfaces a synchronous writer throw as a failed save', async () => {
    const queue = createOfficeSaveQueue<string>(() => {
      throw new Error('sync');
    });
    queue.edit('x');
    const outcome = await queue.save();
    expect(outcome.status).toBe('failed');
    expect(queue.isSaving()).toBe(false);
  });
});
