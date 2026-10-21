import { getApiUrl } from '@/lib/config';
import { getAuthHeader } from '@/stores/auth';
import { SYSTEM_API } from './system-api';
import { parseSseFrames, type TrafficFrame } from './system-traffic-model';

/**
 * Read the live traffic stream until it ends or ``signal`` aborts. Raw fetch, like
 * chat streaming: authFetch would keep the network indicator busy for the whole stream.
 */
export async function streamTraffic({
  signal,
  onFrame,
  maxSeconds = 900,
}: {
  signal: AbortSignal;
  onFrame: (frame: TrafficFrame) => void;
  maxSeconds?: number;
}): Promise<void> {
  const res = await fetch(`${getApiUrl()}${SYSTEM_API}/traffic/stream?max_seconds=${maxSeconds}`, {
    headers: { ...getAuthHeader(), Accept: 'text/event-stream' },
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(res.status === 403 ? 'Platform super admin role required' : `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    const { frames, rest } = parseSseFrames(buffer);
    buffer = rest;
    for (const frame of frames) onFrame(frame as TrafficFrame);
  }
}
