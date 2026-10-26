// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AuditEntry } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '../../system-render';
import { allowAll, fakeApi } from '../service-fixtures';
import { AuditView, filterByOperation, outcome } from './audit';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const entry = (over: Partial<AuditEntry> = {}): AuditEntry => ({
  at: '2026-10-19T10:00:00Z',
  actor_id: 'usr_1',
  actor: 'Ada',
  operation: 'attach_policy',
  resource_id: 'builtin.admin/usr_2',
  detail: 'at abi:acme:-',
  phase: 'succeeded',
  error: '',
  ...over,
});

describe('audit', () => {
  it('words the outcome, with the error type of a failure', () => {
    expect(outcome(entry())).toBe('succeeded');
    expect(outcome(entry({ phase: 'requested' }))).toBe('requested');
    expect(outcome(entry({ phase: 'failed', error: 'PermissionDeniedError' }))).toBe(
      'failed (PermissionDeniedError)',
    );
  });

  it('filters by operation text', () => {
    const all = [entry(), entry({ operation: 'create_key' })];
    expect(filterByOperation(all, 'KEY').map((e) => e.operation)).toEqual(['create_key']);
    expect(filterByOperation(all, '  ')).toHaveLength(2);
  });

  it('shows the history and filters it', async () => {
    const audit = vi.fn(() =>
      Promise.resolve({ items: [entry(), entry({ operation: 'create_key', resource_id: 'sa_1/k1', detail: '' })] }),
    );
    mounted = await mount(AuditView, { api: fakeApi({ audit }), can: allowAll });
    await mounted.flush();
    expect(document.querySelectorAll('tbody tr')).toHaveLength(2);
    await mounted.type(document.querySelector('[aria-label="Operation"]'), 'create_key');
    expect(document.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(document.body.textContent).toContain('sa_1/k1');
  });
});
