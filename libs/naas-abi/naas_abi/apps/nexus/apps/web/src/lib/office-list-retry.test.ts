import { describe, expect, it, vi } from 'vitest';

import {
  isRetryableOfficeListStatus,
  isTransientOfficeListError,
  withOfficeListRetry,
} from './office-list-retry';

describe('isTransientOfficeListError', () => {
  it('retries browser and gateway failures', () => {
    expect(isTransientOfficeListError(new Error('Failed to fetch'))).toBe(true);
    expect(isTransientOfficeListError(new Error('Failed (502)'))).toBe(true);
    expect(isTransientOfficeListError(new Error('Failed (503)'))).toBe(true);
    expect(isTransientOfficeListError('timeout')).toBe(true);
    expect(isTransientOfficeListError(new Error('The user aborted a request.'))).toBe(true);
  });

  it('does not retry a real not-found or validation message', () => {
    expect(isTransientOfficeListError(new Error('Failed (404)'))).toBe(false);
    expect(isTransientOfficeListError(new Error('Git repo is missing'))).toBe(false);
  });
});

describe('isRetryableOfficeListStatus', () => {
  it('retries 429 and 5xx only', () => {
    expect(isRetryableOfficeListStatus(429)).toBe(true);
    expect(isRetryableOfficeListStatus(502)).toBe(true);
    expect(isRetryableOfficeListStatus(404)).toBe(false);
    expect(isRetryableOfficeListStatus(200)).toBe(false);
  });
});

describe('withOfficeListRetry', () => {
  it('returns the first success and does not keep calling', async () => {
    const run = vi
      .fn()
      .mockRejectedValueOnce(new Error('Failed to fetch'))
      .mockResolvedValueOnce(['deck-a']);
    await expect(withOfficeListRetry(run, { delayMs: 1 })).resolves.toEqual(['deck-a']);
    expect(run).toHaveBeenCalledTimes(2);
  });

  it('stops on a non-transient error', async () => {
    const run = vi.fn().mockRejectedValue(new Error('Failed (404)'));
    await expect(withOfficeListRetry(run, { delayMs: 1, attempts: 4 })).rejects.toThrow(
      'Failed (404)',
    );
    expect(run).toHaveBeenCalledTimes(1);
  });
});
