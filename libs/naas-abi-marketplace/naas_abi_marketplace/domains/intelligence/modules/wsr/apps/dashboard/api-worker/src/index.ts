import { Container } from "@cloudflare/containers";

// One Container instance manages the FastAPI process lifecycle.
// Requests arrive at the Worker, get forwarded to the container on port 8080,
// and responses stream back transparently.
export class WSRApiContainer extends Container {
  defaultPort = 8080;
  // Container sleeps after 5 minutes of inactivity to save costs.
  // On the next request it wakes in ~2-3 seconds.
  sleepAfter = "5m";

  override onStart(): void {
    console.log("[wsr-api] container started");
  }
  override onStop(): void {
    console.log("[wsr-api] container stopped");
  }
  override onError(error: unknown): void {
    console.error("[wsr-api] container error:", error);
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Route all traffic to a single named container instance.
    // Swap getByName for getRandom(env.WSR_API, N) if you need horizontal scale.
    const container = env.WSR_API.getByName("wsr-api-0");
    return container.fetch(request);
  },
} satisfies ExportedHandler<Env>;
