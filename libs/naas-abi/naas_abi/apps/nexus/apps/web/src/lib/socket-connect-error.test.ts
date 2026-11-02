import { describe, expect, it } from 'vitest';
import { classifySocketConnectError } from './socket-connect-error';

describe('classifySocketConnectError', () => {
  it('treats an unreachable or restarting API as transient', () => {
    expect(classifySocketConnectError('timeout')).toBe('transient');
    expect(classifySocketConnectError('xhr poll error')).toBe('transient');
    expect(classifySocketConnectError('websocket error')).toBe('transient');
  });

  it('detects auth failures from the status or the message', () => {
    expect(classifySocketConnectError('anything', 401)).toBe('auth');
    expect(classifySocketConnectError('Unauthorized')).toBe('auth');
    expect(classifySocketConnectError('403 Forbidden')).toBe('auth');
  });

  it('leaves anything else to be reported', () => {
    expect(classifySocketConnectError('Invalid namespace')).toBe('other');
    expect(classifySocketConnectError(undefined)).toBe('other');
  });
});
