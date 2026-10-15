// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { modulesView } from './system-fixtures';
import { mount, type Mounted } from './system-render';
import { SystemModules } from './system-modules';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('SystemModules', () => {
  it('shows engine modules with their jobs', async () => {
    mounted = await mount(SystemModules, { view: modulesView });
    const engine = mounted.host.querySelector('[data-engine-module="acme.jobs"]');

    expect(engine?.textContent).toContain('Acme jobs');
    expect(engine?.textContent).toContain('cron 0 0 2 * * * UTC');
  });

  it('groups replicas of a remote module and expands to its instances', async () => {
    mounted = await mount(SystemModules, { view: modulesView });
    const group = mounted.host.querySelector('[data-remote-module="ops.researcher"]');

    expect(group?.textContent).toContain('1 READY');
    expect(group?.textContent).toContain('1 STARTING');
    expect(group?.textContent).toContain('Researcher');
    expect(group?.textContent).toContain('every 10m');
    expect(mounted.host.textContent).not.toContain('r-2');

    await mounted.click(group?.querySelector('button') ?? null);

    expect(mounted.host.textContent).toContain('r-2');
  });

  it('says why remote modules are missing', async () => {
    const view = { ...modulesView, remote: [], sources: { discovery: { available: false, reason: 'nats.discovery is not configured' } } };
    mounted = await mount(SystemModules, { view });

    expect(mounted.host.querySelector('.system-source-note')?.textContent).toContain('nats.discovery is not configured');
  });
});

describe('SystemModules eviction', () => {
  it('evicts an instance after its id is typed back, through the audited Data API', async () => {
    const { vi } = await import('vitest');
    const remove = vi.fn(() => Promise.resolve({ ok: true as const, data: null }));
    const onChanged = vi.fn();
    const api = { remove } as unknown as import('./data/data-api').DataApi;
    mounted = await mount(SystemModules, { view: modulesView, api, onChanged });
    const group = mounted.host.querySelector('[data-remote-module="ops.researcher"]');
    await mounted.click(group?.querySelector('button') ?? null);

    const evict = [...document.querySelectorAll('button')].find((b) => b.getAttribute('aria-label') === 'Evict r-2');
    await mounted.click(evict ?? null);
    const confirm = () => [...document.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Evict instance');
    expect(confirm()?.disabled).toBe(true);

    await mounted.type(document.querySelector('[aria-label="Type the id to confirm"]'), 'ops.researcher/r-2');
    await mounted.click(confirm() ?? null);
    await mounted.flush();

    expect(remove).toHaveBeenCalledWith('discovery', 'ops.researcher/r-2', 'ops.researcher/r-2');
    expect(onChanged).toHaveBeenCalled();
    expect(document.body.textContent).not.toContain('Evict instance');
  });
});
