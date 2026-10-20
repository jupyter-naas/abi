/**
 * Process-local AISStream client. One socket per Node process.
 * Cloudflare Pages isolates cannot hold this cache; nexus-web `next start` can.
 */
import {
  ingestAisEnvelope,
  parseAisFrame,
  pruneAisVessels,
  type AisVessel,
} from './store';

export type AisStreamStatus =
  | 'missing-key'
  | 'unavailable'
  | 'connecting'
  | 'live'
  | 'auth-failed'
  | 'error';

type AisStreamState = {
  vessels: Map<string, AisVessel>;
  socket: WebSocket | null;
  generation: number;
  status: AisStreamStatus;
  error: string | null;
  lastMessageAt: number | null;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  backoffMs: number;
};

const AISSTREAM_URL = 'wss://stream.aisstream.io/v0/stream';
const BACKOFF = [5_000, 15_000, 30_000, 60_000];

const state: AisStreamState = {
  vessels: new Map(),
  socket: null,
  generation: 0,
  status: 'missing-key',
  error: null,
  lastMessageAt: null,
  reconnectTimer: null,
  backoffMs: BACKOFF[0],
};

export function aisStreamApiKey(): string {
  return (
    process.env.AISSTREAM_API_KEY?.trim() ||
    process.env.AIS_API_KEY?.trim() ||
    ''
  );
}

export function aisStreamSnapshot(): {
  vessels: Map<string, AisVessel>;
  status: AisStreamStatus;
  error: string | null;
  lastMessageAt: number | null;
} {
  pruneAisVessels(state.vessels);
  return {
    vessels: state.vessels,
    status: state.status,
    error: state.error,
    lastMessageAt: state.lastMessageAt,
  };
}

export function ensureAisStream(): void {
  const key = aisStreamApiKey();
  if (!key) {
    disconnectAisStream();
    state.status = 'missing-key';
    state.error = 'AISSTREAM_API_KEY is not set on the nexus-web runtime.';
    return;
  }
  if (typeof WebSocket === 'undefined') {
    state.status = 'unavailable';
    state.error =
      'AIS live cache needs a long-lived Node server. This runtime cannot hold the AISStream socket.';
    return;
  }
  const socket = state.socket;
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }
  connectAisStream(key);
}

function connectAisStream(key: string): void {
  const generation = ++state.generation;
  state.status = 'connecting';
  state.error = null;
  let socket: WebSocket;
  try {
    socket = new WebSocket(process.env.AISSTREAM_URL || AISSTREAM_URL);
  } catch (err) {
    state.status = 'error';
    state.error = err instanceof Error ? err.message : 'AISStream connect failed';
    scheduleReconnect();
    return;
  }
  state.socket = socket;

  socket.addEventListener('open', () => {
    if (generation !== state.generation) return;
    socket.send(
      JSON.stringify({
        APIKey: key,
        BoundingBoxes: [
          [
            [-90, -180],
            [90, 180],
          ],
        ],
        FilterMessageTypes: [
          'PositionReport',
          'StandardClassBPositionReport',
          'ExtendedClassBPositionReport',
          'ShipStaticData',
          'StaticDataReport',
        ],
      }),
    );
  });

  socket.addEventListener('message', (event) => {
    if (generation !== state.generation) return;
    const text = typeof event.data === 'string' ? event.data : null;
    if (!text) return;
    const parsed = parseAisFrame(text);
    if (parsed.kind === 'error') {
      state.status = 'auth-failed';
      state.error = parsed.message;
      socket.close();
      return;
    }
    if (parsed.kind !== 'data') return;
    if (ingestAisEnvelope(state.vessels, parsed.envelope)) {
      state.lastMessageAt = Date.now();
      state.status = 'live';
      state.backoffMs = BACKOFF[0];
    }
  });

  socket.addEventListener('close', () => {
    if (generation !== state.generation) return;
    state.socket = null;
    if (state.status === 'auth-failed' || state.status === 'missing-key') return;
    if (state.status !== 'unavailable') {
      state.status = 'error';
      state.error = state.error || 'AISStream socket closed.';
      scheduleReconnect();
    }
  });

  socket.addEventListener('error', () => {
    if (generation !== state.generation) return;
    if (state.status === 'auth-failed') return;
    state.status = 'error';
    state.error = 'AISStream socket error.';
  });
}

function scheduleReconnect(): void {
  if (state.reconnectTimer) return;
  const wait = state.backoffMs;
  state.backoffMs = BACKOFF[Math.min(BACKOFF.indexOf(wait) + 1, BACKOFF.length - 1)] ?? wait;
  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null;
    if (aisStreamApiKey()) connectAisStream(aisStreamApiKey());
  }, wait);
  state.reconnectTimer.unref?.();
}

function disconnectAisStream(): void {
  state.generation += 1;
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }
  try {
    state.socket?.close();
  } catch {
    // Ignore teardown races.
  }
  state.socket = null;
  state.vessels.clear();
  state.lastMessageAt = null;
}

export function resetAisStreamForTests(): void {
  disconnectAisStream();
  state.status = 'missing-key';
  state.error = null;
  state.backoffMs = BACKOFF[0];
}
