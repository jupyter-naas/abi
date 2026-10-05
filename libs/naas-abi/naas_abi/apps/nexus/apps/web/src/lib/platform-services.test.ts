import { describe, expect, it } from 'vitest';
import { describePlatformServices } from './platform-services';

describe('describePlatformServices', () => {
  it('links a service to the web UI of its adapter', () => {
    const [row] = describePlatformServices([{ id: 'triple_store', adapters: ['apache_jena_tdb2'] }]);
    expect(row.label).toBe('Triple store');
    expect(row.webUi?.id).toBe('fuseki');
  });

  it('has no web UI when the adapter has none', () => {
    const [row] = describePlatformServices([{ id: 'triple_store', adapters: ['oxigraph'] }]);
    expect(row.webUi).toBeUndefined();
  });

  it('describes services without an adapter and unknown services', () => {
    const [registry, unknown] = describePlatformServices([
      { id: 'model_registry', adapters: [] },
      { id: 'new_thing', adapters: ['x'] },
    ]);
    expect(registry.label).toBe('Model registry');
    expect(registry.webUi).toBeUndefined();
    expect(unknown.label).toBe('New thing');
  });
});
