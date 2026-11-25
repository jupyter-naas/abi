import { describe, expect, it } from 'vitest';
import { loadServiceView, loadedServiceView } from './registry';

// `/settings/data/<name>` passes an unknown name through (`serviceForPage`): a name that is
// also a property of every object must get the generic view, never a crash.
describe('service views by name', () => {
  it.each(['toString', 'constructor', '__proto__', 'hasOwnProperty', 'valueOf'])(
    '%s, a property of every object, is an unknown service',
    async (name) => {
      expect(loadedServiceView(name)?.name).toBe(name);
      await expect(loadServiceView(name)).resolves.toMatchObject({ name });
    },
  );

  it('a service with a view of its own still waits for it', async () => {
    expect(loadedServiceView('secret') === null || loadedServiceView('secret')?.name === 'secret').toBe(true);
    await expect(loadServiceView('secret')).resolves.toMatchObject({ name: 'secret' });
  });
});
