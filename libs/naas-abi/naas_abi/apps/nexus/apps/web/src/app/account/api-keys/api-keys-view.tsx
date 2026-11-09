import { Check, Copy, Key, Trash2 } from 'lucide-react';
import {
  ACCESS_LABELS,
  ApiKey,
  ApiKeyAccess,
  CUSTOM_SCOPE_EXAMPLE,
  CreatedApiKey,
  EXPIRY_CHOICES,
  NAME_MAX_LENGTH,
  STATUS_LABELS,
  formatKeyDate,
  usageExamples,
} from '@/lib/api-keys';

/** What the create form holds; the page owns it. */
export type CreateFormValues = {
  name: string;
  expiresInDays: number;
  access: ApiKeyAccess;
  scopeText: string;
};

type CreateKeyFormProps = {
  values: CreateFormValues;
  pending: boolean;
  error: string | null;
  onChange: (values: CreateFormValues) => void;
  onSubmit: () => void;
  onCancel: () => void;
};

export function CreateKeyForm({
  values,
  pending,
  error,
  onChange,
  onSubmit,
  onCancel,
}: CreateKeyFormProps) {
  const canSubmit = !pending && values.name.trim().length > 0;
  return (
    <form
      className="account-api-keys-create-form"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
    >
      <h3 className="account-api-keys-create-form-title">Create New API Key</h3>
      <div className="account-api-keys-create-form-row">
        <input
          type="text"
          value={values.name}
          maxLength={NAME_MAX_LENGTH}
          onChange={(event) => onChange({ ...values, name: event.target.value })}
          placeholder="Key name (e.g., Production, CI/CD)"
          aria-label="Key name"
          className="account-api-keys-create-form-input"
        />
        <select
          value={values.expiresInDays}
          onChange={(event) => onChange({ ...values, expiresInDays: Number(event.target.value) })}
          aria-label="Expires after"
          className="account-api-keys-create-form-select"
        >
          {EXPIRY_CHOICES.map((choice) => (
            <option key={choice.days} value={choice.days}>
              Expires in {choice.label}
            </option>
          ))}
        </select>
        <select
          value={values.access}
          onChange={(event) => onChange({ ...values, access: event.target.value as ApiKeyAccess })}
          aria-label="Access"
          className="account-api-keys-create-form-select"
        >
          <option value="full">{ACCESS_LABELS.full} (as you)</option>
          <option value="read">{ACCESS_LABELS.read} (reads and lists)</option>
          <option value="custom">{ACCESS_LABELS.custom} (your own statements)</option>
        </select>
      </div>
      {values.access === 'custom' && (
        <div className="account-api-keys-create-form-scope">
          <label htmlFor="api-key-scope" className="account-api-keys-create-form-hint">
            Statements the key is limited to: a JSON array of{' '}
            <code>{'{ "effect": "Allow", "actions": [...], "resources": [...] }'}</code>. The key
            can never do more than you can.
          </label>
          <textarea
            id="api-key-scope"
            value={values.scopeText}
            onChange={(event) => onChange({ ...values, scopeText: event.target.value })}
            placeholder={CUSTOM_SCOPE_EXAMPLE}
            rows={6}
            spellCheck={false}
            className="account-api-keys-create-form-textarea"
          />
        </div>
      )}
      {error && (
        <p role="alert" className="account-api-keys-error">
          {error}
        </p>
      )}
      <div className="account-api-keys-create-form-row">
        <button
          type="submit"
          disabled={!canSubmit}
          className="account-api-keys-create-form-submit"
        >
          {pending ? 'Creating…' : 'Create'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={pending}
          className="account-api-keys-create-form-cancel"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

type SecretPanelProps = {
  created: CreatedApiKey;
  apiBase: string;
  copied: boolean;
  onCopy: () => void;
  onDismiss: () => void;
};

/** The key just made, shown once, with how to use it. */
export function SecretPanel({ created, apiBase, copied, onCopy, onDismiss }: SecretPanelProps) {
  const examples = usageExamples(created.secret, apiBase);
  return (
    <section className="account-api-keys-secret" aria-label="New API key">
      <h3 className="account-api-keys-secret-title">Copy your new key: “{created.key.name}”</h3>
      <p role="alert" className="account-api-keys-secret-warning">
        This is the only time the key is shown. It is not stored: if you lose it, revoke it and
        create another.
      </p>
      <div className="account-api-keys-key-row">
        <code className="account-api-keys-secret-code">{created.secret}</code>
        <button
          type="button"
          onClick={onCopy}
          className="account-api-keys-icon-button"
          aria-label="Copy key"
        >
          {copied ? (
            <Check size={14} className="account-api-keys-icon-button-copied" />
          ) : (
            <Copy size={14} />
          )}
        </button>
      </div>
      <p className="account-api-keys-usage-description">Use it as a bearer token:</p>
      <pre className="account-api-keys-usage-code">{examples.bearer}</pre>
      <p className="account-api-keys-usage-description">
        Or exchange it for a short-lived access token:
      </p>
      <pre className="account-api-keys-usage-code">{examples.token}</pre>
      <button type="button" onClick={onDismiss} className="account-api-keys-create-form-cancel">
        I have copied it
      </button>
    </section>
  );
}

type ApiKeysTableProps = {
  keys: ApiKey[];
  confirmingId: string | null;
  revokingId: string | null;
  onAskRevoke: (id: string) => void;
  onCancelRevoke: () => void;
  onRevoke: (id: string) => void;
};

export function ApiKeysTable({
  keys,
  confirmingId,
  revokingId,
  onAskRevoke,
  onCancelRevoke,
  onRevoke,
}: ApiKeysTableProps) {
  if (keys.length === 0) {
    return (
      <div className="account-api-keys-empty">
        <Key size={32} className="account-api-keys-empty-icon" />
        <p className="account-api-keys-empty-text">No API keys created yet</p>
      </div>
    );
  }
  return (
    <table className="account-api-keys-table">
      <thead>
        <tr className="account-api-keys-table-head-row">
          <th className="account-api-keys-table-head-cell">Name</th>
          <th className="account-api-keys-table-head-cell">Key</th>
          <th className="account-api-keys-table-head-cell">Access</th>
          <th className="account-api-keys-table-head-cell">Created</th>
          <th className="account-api-keys-table-head-cell">Last Used</th>
          <th className="account-api-keys-table-head-cell">Expires</th>
          <th className="account-api-keys-table-head-cell account-api-keys-table-head-cell-actions">
            Actions
          </th>
        </tr>
      </thead>
      <tbody>
        {keys.map((apiKey) => (
          <tr key={apiKey.id} className="account-api-keys-table-row">
            <td className="account-api-keys-table-cell account-api-keys-table-cell-name">
              {apiKey.name}
              <span
                className={`account-api-keys-status account-api-keys-status-${apiKey.status}`}
              >
                {STATUS_LABELS[apiKey.status]}
              </span>
            </td>
            <td className="account-api-keys-table-cell">
              <code className="account-api-keys-key-code">{apiKey.prefix}…</code>
            </td>
            <td className="account-api-keys-table-cell account-api-keys-table-cell-meta">
              {ACCESS_LABELS[apiKey.access]}
            </td>
            <td className="account-api-keys-table-cell account-api-keys-table-cell-meta">
              {formatKeyDate(apiKey.created_at, '—')}
            </td>
            <td className="account-api-keys-table-cell account-api-keys-table-cell-meta">
              {formatKeyDate(apiKey.last_used_at, 'Never')}
            </td>
            <td className="account-api-keys-table-cell account-api-keys-table-cell-meta">
              {apiKey.status === 'revoked'
                ? `Revoked ${formatKeyDate(apiKey.revoked_at, '')}`.trim()
                : formatKeyDate(apiKey.expires_at, 'Never')}
            </td>
            <td className="account-api-keys-table-cell account-api-keys-table-cell-actions">
              {apiKey.status === 'revoked' ? null : confirmingId === apiKey.id ? (
                <span className="account-api-keys-confirm">
                  Revoke this key?
                  <button
                    type="button"
                    onClick={() => onRevoke(apiKey.id)}
                    disabled={revokingId === apiKey.id}
                    className="account-api-keys-confirm-yes"
                  >
                    {revokingId === apiKey.id ? 'Revoking…' : 'Revoke'}
                  </button>
                  <button
                    type="button"
                    onClick={onCancelRevoke}
                    disabled={revokingId === apiKey.id}
                    className="account-api-keys-create-form-cancel"
                  >
                    Keep
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => onAskRevoke(apiKey.id)}
                  className="account-api-keys-icon-button account-api-keys-icon-button-delete"
                  aria-label={`Revoke key ${apiKey.name}`}
                >
                  <Trash2 size={16} />
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
