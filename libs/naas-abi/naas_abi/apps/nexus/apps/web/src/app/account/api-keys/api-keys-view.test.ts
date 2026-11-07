import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { ApiKey, CreatedApiKey } from '@/lib/api-keys';
import {
  ApiKeysTable,
  CreateKeyForm,
  type CreateFormValues,
  SecretPanel,
} from './api-keys-view';

const key = (over: Partial<ApiKey> = {}): ApiKey => ({
  id: 'abcdefghijklmnop',
  name: 'CI',
  prefix: 'abi_pk_abcdefghijklmnop',
  created_at: '2026-10-01T10:00:00Z',
  expires_at: '2027-10-01T10:00:00Z',
  last_used_at: null,
  revoked_at: null,
  status: 'active',
  access: 'full',
  scope: null,
  ...over,
});

const noop = vi.fn();
const table = (keys: ApiKey[], over: Record<string, unknown> = {}) =>
  renderToStaticMarkup(
    createElement(ApiKeysTable, {
      keys,
      confirmingId: null,
      revokingId: null,
      onAskRevoke: noop,
      onCancelRevoke: noop,
      onRevoke: noop,
      ...over,
    }),
  );

describe('ApiKeysTable', () => {
  it('says so when there are no keys', () => {
    expect(table([])).toContain('No API keys created yet');
  });

  it('lists the name, the prefix, the status and the access, never a secret', () => {
    const html = table([
      key(),
      key({ id: 'b', name: 'Reports', prefix: 'abi_pk_b', access: 'read' }),
      key({ id: 'c', name: 'Custom', prefix: 'abi_pk_c', access: 'custom', scope: [] }),
    ]);
    expect(html).toContain('CI');
    expect(html).toContain('abi_pk_abcdefghijklmnop…');
    expect(html).toContain('Full access');
    expect(html).toContain('Read only');
    expect(html).toContain('Custom');
    expect(html).toContain('Active');
    expect(html).toContain('Never'); // never used
    expect(html).not.toMatch(/abi_pk_[a-z]{16}_/);
  });

  it('shows a revoked key as revoked, with nothing left to revoke', () => {
    const html = table([key({ status: 'revoked', revoked_at: '2026-10-02T00:00:00Z' })]);
    expect(html).toContain('Revoked');
    expect(html).not.toContain('aria-label="Revoke key CI"');
  });

  it('shows an expired key as expired', () => {
    expect(table([key({ status: 'expired' })])).toContain('Expired');
  });

  it('asks before revoking, then revokes the one asked about', () => {
    const asking = table([key(), key({ id: 'b', name: 'Other' })], { confirmingId: 'abcdefghijklmnop' });
    expect(asking).toContain('Revoke this key?');
    expect(asking.match(/Revoke this key\?/g)).toHaveLength(1);
    expect(asking).toContain('aria-label="Revoke key Other"');
    expect(table([key()], { confirmingId: 'abcdefghijklmnop', revokingId: 'abcdefghijklmnop' })).toContain(
      'Revoking…',
    );
  });
});

const values = (over: Partial<CreateFormValues> = {}): CreateFormValues => ({
  name: '',
  expiresInDays: 365,
  access: 'full',
  scopeText: '',
  ...over,
});

const form = (v: CreateFormValues, over: Record<string, unknown> = {}) =>
  renderToStaticMarkup(
    createElement(CreateKeyForm, {
      values: v,
      pending: false,
      error: null,
      onChange: noop,
      onSubmit: noop,
      onCancel: noop,
      ...over,
    }),
  );

describe('CreateKeyForm', () => {
  it('offers the expiries and the three kinds of access', () => {
    const html = form(values());
    for (const text of ['30 days', '90 days', '1 year', 'Full access', 'Read only', 'Custom']) {
      expect(html).toContain(text);
    }
    expect(html).not.toContain('<textarea');
  });

  it('asks for statements only for a custom key', () => {
    expect(form(values({ access: 'custom' }))).toContain('<textarea');
    expect(form(values({ access: 'read' }))).not.toContain('<textarea');
  });

  it('cannot be submitted without a name, nor while it is pending', () => {
    expect(form(values())).toMatch(/<button type="submit" disabled=""/);
    expect(form(values({ name: 'CI' }))).not.toMatch(/<button type="submit" disabled=""/);
    const pending = form(values({ name: 'CI' }), { pending: true });
    expect(pending).toMatch(/<button type="submit" disabled=""/);
    expect(pending).toContain('Creating…');
  });

  it('shows what went wrong', () => {
    expect(form(values({ name: 'CI' }), { error: 'The statements are not valid JSON.' })).toContain(
      'The statements are not valid JSON.',
    );
  });
});

describe('SecretPanel', () => {
  const created: CreatedApiKey = { key: key(), secret: 'abi_pk_abcdefghijklmnop_s3cr3t' };
  const panel = (copied = false) =>
    renderToStaticMarkup(
      createElement(SecretPanel, {
        created,
        apiBase: 'https://api.example.com',
        copied,
        onCopy: noop,
        onDismiss: noop,
      }),
    );

  it('shows the secret with a warning that it is shown once', () => {
    const html = panel();
    expect(html).toContain('abi_pk_abcdefghijklmnop_s3cr3t');
    expect(html).toContain('only time the key is shown');
    expect(html).toContain('aria-label="Copy key"');
  });

  it('shows how to use it, bearer and token endpoint', () => {
    const html = panel();
    expect(html).toContain('Authorization: Bearer abi_pk_abcdefghijklmnop_s3cr3t');
    expect(html).toContain('https://api.example.com/api/iam/token');
    expect(html).toContain('grant_type=client_credentials');
  });
});
