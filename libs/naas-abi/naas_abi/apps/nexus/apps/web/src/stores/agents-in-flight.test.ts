import { describe, expect, it } from 'vitest';
import { joinAgentsFetch } from './agents';

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

describe('joinAgentsFetch', () => {
  it('sends one read for callers that ask at the same time', async () => {
    const gate = deferred();
    let runs = 0;
    const run = () => {
      runs += 1;
      return gate.promise;
    };
    const first = joinAgentsFetch('ws-a', false, run);
    const second = joinAgentsFetch('ws-a', false, run);
    expect(second).toBe(first);
    gate.resolve();
    await Promise.all([first, second]);
    expect(runs).toBe(1);
  });

  it('lets a sync in flight answer a read, not the other way around', async () => {
    const sync = deferred();
    const read = deferred();
    let reads = 0;
    const syncing = joinAgentsFetch('ws-b', true, () => sync.promise);
    expect(joinAgentsFetch('ws-b', false, () => ((reads += 1), read.promise))).toBe(syncing);
    sync.resolve();
    await syncing;

    const reading = joinAgentsFetch('ws-b', false, () => ((reads += 1), read.promise));
    let syncs = 0;
    const syncAfter = joinAgentsFetch('ws-b', true, () => ((syncs += 1), Promise.resolve()));
    expect(syncAfter).not.toBe(reading);
    read.resolve();
    await Promise.all([reading, syncAfter]);
    expect(reads).toBe(1);
    expect(syncs).toBe(1);
  });

  it('asks again once the call settled, failed or not', async () => {
    let runs = 0;
    await joinAgentsFetch('ws-c', false, async () => {
      runs += 1;
    });
    await joinAgentsFetch('ws-c', false, async () => {
      runs += 1;
      throw new Error('down');
    }).catch(() => undefined);
    await joinAgentsFetch('ws-c', false, async () => {
      runs += 1;
    });
    expect(runs).toBe(3);
  });

  it('keeps workspaces apart', () => {
    const gate = deferred();
    const a = joinAgentsFetch('ws-d', false, () => gate.promise);
    const b = joinAgentsFetch('ws-e', false, () => gate.promise);
    expect(a).not.toBe(b);
    gate.resolve();
  });
});
