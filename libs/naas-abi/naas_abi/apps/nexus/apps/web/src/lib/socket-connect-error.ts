export type SocketConnectErrorKind = 'auth' | 'transient' | 'other';

/**
 * Sort a Socket.IO `connect_error`. socket.io-client reports an unreachable or
 * restarting API (e.g. a dev reload) as "timeout", "xhr poll error" or
 * "websocket error": those are retried, not failures to surface.
 */
export function classifySocketConnectError(
  message: string | null | undefined,
  status?: number,
): SocketConnectErrorKind {
  const text = (message || '').toLowerCase();
  if (
    status === 401 ||
    status === 403 ||
    text.includes('401') ||
    text.includes('403') ||
    text.includes('unauthorized') ||
    text.includes('forbidden')
  ) {
    return 'auth';
  }
  if (
    text === 'timeout' ||
    text.includes('xhr poll error') ||
    text.includes('websocket error') ||
    text.includes('transport error') ||
    text.includes('transport close')
  ) {
    return 'transient';
  }
  return 'other';
}
