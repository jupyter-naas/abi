// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { servicesView } from './system-fixtures';
import { mount, type Mounted } from './system-render';
import { SystemServices } from './system-services';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('SystemServices', () => {
  it('lists every service with its adapters, status and totals', async () => {
    mounted = await mount(SystemServices, { view: servicesView });
    const rows = [...mounted.host.querySelectorAll('[data-service]')];

    expect(rows.map((r) => r.getAttribute('data-service'))).toEqual(['document', 'secret', 'bus']);
    expect(rows[0].textContent).toContain('postgresql');
    expect(rows[0].textContent).toContain('Serving');
    expect(rows[0].textContent).toContain('2'); // instances
    expect(rows[1].textContent).toContain('No responders');
    expect(rows[2].textContent).toContain('Not on NATS');
  });

  it('expands a service into its instances and endpoints', async () => {
    mounted = await mount(SystemServices, { view: servicesView });
    expect(mounted.host.textContent).not.toContain('abi.svc.document.v1.get');

    await mounted.click(mounted.host.querySelector('[data-service="document"] button'));

    expect(mounted.host.textContent).toContain('abi.svc.document.v1.get');
    expect(mounted.host.textContent).toContain('d1');
  });

  it('says why live stats are missing', async () => {
    const view = { ...servicesView, sources: { nats: { available: false, reason: 'NATS mode is off' } } };
    mounted = await mount(SystemServices, { view });

    expect(mounted.host.querySelector('.system-source-note')?.textContent).toContain('NATS mode is off');
  });
});
