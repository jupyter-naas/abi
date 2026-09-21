/** Small, in-memory read cache. Never persisted; callers own authorization and invalidation. */
export class GraphReadCache {
  private entries = new Map<string, { data: unknown; expires: number }>();
  generation = 0;
  constructor(private maxEntries = 32, private ttl = 30_000, private now = Date.now) {}

  get<T>(key: string): T | undefined {
    const entry = this.entries.get(key);
    if (!entry) return undefined;
    if (entry.expires <= this.now()) {
      this.entries.delete(key);
      return undefined;
    }
    this.entries.delete(key);
    this.entries.set(key, entry);
    return entry.data as T;
  }

  set(key: string, data: unknown, generation: number) {
    // A request begun before refresh/logout must not repopulate the cache.
    if (generation !== this.generation) return;
    this.entries.delete(key);
    this.entries.set(key, { data, expires: this.now() + this.ttl });
    while (this.entries.size > this.maxEntries) this.entries.delete(this.entries.keys().next().value!);
  }

  delete(key: string) { this.entries.delete(key); }
  clear() { this.entries.clear(); this.generation += 1; }
}
