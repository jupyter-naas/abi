'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import {
  ApiKey,
  ApiKeysError,
  CreatedApiKey,
  DEFAULT_EXPIRY_DAYS,
  MAX_ACTIVE_KEYS,
  activeKeyCount,
  createApiKey,
  listApiKeys,
  parseScopeJson,
  revokeApiKey,
} from '@/lib/api-keys';
import { getApiUrl } from '@/lib/config';
import { AccountPageHeader } from '../components/account-page-header';
import { AccountSectionCard } from '../components/account-section-card';
import { ApiKeysTable, CreateFormValues, CreateKeyForm, SecretPanel } from './api-keys-view';
import './api-keys.css';

const EMPTY_FORM: CreateFormValues = {
  name: '',
  expiresInDays: DEFAULT_EXPIRY_DAYS,
  access: 'full',
  scopeText: '',
};

function messageOf(error: unknown, fallback: string): string {
  return error instanceof ApiKeysError || error instanceof Error ? error.message : fallback;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateFormValues>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  // The key just made: its secret lives in memory until dismissed, never in storage.
  const [created, setCreated] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      setKeys(await listApiKeys());
    } catch (error) {
      setLoadError(messageOf(error, 'Could not load your API keys.'));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async () => {
    setCreateError(null);
    let scope;
    if (form.access === 'custom') {
      const parsed = parseScopeJson(form.scopeText);
      if (!parsed.ok) {
        setCreateError(parsed.error);
        return;
      }
      scope = parsed.scope;
    }
    setCreating(true);
    try {
      const result = await createApiKey({
        name: form.name,
        expiresInDays: form.expiresInDays,
        access: form.access,
        scope,
      });
      setCreated(result);
      setCopied(false);
      setShowCreate(false);
      setForm(EMPTY_FORM);
      setKeys((current) => [result.key, ...(current ?? [])]);
    } catch (error) {
      setCreateError(messageOf(error, 'Could not create the API key.'));
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const handleRevoke = async (id: string) => {
    setRevokeError(null);
    setRevokingId(id);
    try {
      const revoked = await revokeApiKey(id);
      setKeys((current) => (current ?? []).map((key) => (key.id === id ? revoked : key)));
      setConfirmingId(null);
    } catch (error) {
      setRevokeError(messageOf(error, 'Could not revoke the API key.'));
    } finally {
      setRevokingId(null);
    }
  };

  const atLimit = keys !== null && activeKeyCount(keys) >= MAX_ACTIVE_KEYS;

  return (
    <div className="account-api-keys-page">
      <AccountPageHeader
        title="API Keys"
        subtitle="Manage API keys for programmatic access to NEXUS"
        actions={
          <button
            onClick={() => {
              setCreateError(null);
              setShowCreate(true);
            }}
            disabled={atLimit}
            title={atLimit ? `You can have ${MAX_ACTIVE_KEYS} active keys: revoke one first` : undefined}
            className="account-api-keys-create-button"
          >
            <Plus size={16} />
            Create Key
          </button>
        }
      />

      {created && (
        <SecretPanel
          created={created}
          apiBase={getApiUrl()}
          copied={copied}
          onCopy={() => void handleCopy()}
          onDismiss={() => setCreated(null)}
        />
      )}

      {showCreate && (
        <AccountSectionCard padded>
          <CreateKeyForm
            values={form}
            pending={creating}
            error={createError}
            onChange={setForm}
            onSubmit={() => void handleCreate()}
            onCancel={() => {
              setShowCreate(false);
              setForm(EMPTY_FORM);
              setCreateError(null);
            }}
          />
        </AccountSectionCard>
      )}

      {revokeError && (
        <p role="alert" className="account-api-keys-error">
          {revokeError}
        </p>
      )}

      <AccountSectionCard flush overflowHidden>
        {loadError ? (
          <div className="account-api-keys-empty">
            <p role="alert" className="account-api-keys-error">
              {loadError}
            </p>
            <button onClick={() => void load()} className="account-api-keys-create-form-cancel">
              Try again
            </button>
          </div>
        ) : keys === null ? (
          <div className="account-api-keys-empty" aria-busy="true">
            <p className="account-api-keys-empty-text">Loading your API keys…</p>
          </div>
        ) : (
          <ApiKeysTable
            keys={keys}
            confirmingId={confirmingId}
            revokingId={revokingId}
            onAskRevoke={setConfirmingId}
            onCancelRevoke={() => setConfirmingId(null)}
            onRevoke={(id) => void handleRevoke(id)}
          />
        )}
      </AccountSectionCard>

      <div className="account-api-keys-usage">
        <h3 className="account-api-keys-usage-title">Using API Keys</h3>
        <p className="account-api-keys-usage-description">
          Send a key as a bearer token on any API route except your account and the keys
          themselves, or exchange it for a short-lived token at <code>/api/iam/token</code>. A key
          expires (a year at most), can be revoked at any time, and never does more than you can.
        </p>
        <code className="account-api-keys-usage-code">
          curl -H "Authorization: Bearer abi_pk_your_api_key" \<br />
          &nbsp;&nbsp;{getApiUrl().replace(/\/+$/, '')}/api/workspaces
        </code>
      </div>
    </div>
  );
}
