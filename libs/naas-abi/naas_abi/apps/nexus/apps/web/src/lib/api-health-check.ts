/** Drop a health result that finished after a newer check already started. */
export function createHealthCheckGate() {
  let latest = 0;
  return {
    begin(): number {
      latest += 1;
      return latest;
    },
    isCurrent(id: number): boolean {
      return id === latest;
    },
  };
}

export const API_HEALTH_POLL_MS = 15_000;
export const API_HEALTH_OFFLINE_POLL_MS = 3_000;
