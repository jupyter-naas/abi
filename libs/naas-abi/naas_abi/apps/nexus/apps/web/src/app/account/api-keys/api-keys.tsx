'use client';

import { useState } from 'react';
import { Plus, Copy, Trash2, Eye, EyeOff, Key, Check } from 'lucide-react';
import { AccountPageHeader } from '../components/account-page-header';
import { AccountSectionCard } from '../components/account-section-card';
import './api-keys.css';

interface ApiKey {
  id: string;
  name: string;
  key: string;
  createdAt: Date;
  lastUsed: Date | null;
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([
    {
      id: '1',
      name: 'Development',
      key: 'nx_dev_a1b2c3d4e5f6g7h8i9j0',
      createdAt: new Date('2024-01-15'),
      lastUsed: new Date('2024-02-01'),
    },
  ]);
  const [showKey, setShowKey] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');

  const handleCopy = (key: string, id: string) => {
    navigator.clipboard.writeText(key);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const handleCreate = () => {
    if (!newKeyName.trim()) return;
    const newKey: ApiKey = {
      id: Math.random().toString(36).substring(2),
      name: newKeyName,
      key: `nx_${Math.random().toString(36).substring(2, 26)}`,
      createdAt: new Date(),
      lastUsed: null,
    };
    setKeys([...keys, newKey]);
    setNewKeyName('');
    setShowCreate(false);
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to revoke this API key?')) {
      setKeys(keys.filter((k) => k.id !== id));
    }
  };

  return (
    <div className="account-api-keys-page">
      <AccountPageHeader
        title="API Keys"
        subtitle="Manage API keys for programmatic access to NEXUS"
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="account-api-keys-create-button"
          >
            <Plus size={16} />
            Create Key
          </button>
        }
      />

      {showCreate && (
        <AccountSectionCard padded>
          <h3 className="account-api-keys-create-form-title">Create New API Key</h3>
          <div className="account-api-keys-create-form-row">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g., Production, CI/CD)"
              className="account-api-keys-create-form-input"
            />
            <button
              onClick={handleCreate}
              className="account-api-keys-create-form-submit"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="account-api-keys-create-form-cancel"
            >
              Cancel
            </button>
          </div>
        </AccountSectionCard>
      )}

      <AccountSectionCard flush overflowHidden>
        {keys.length === 0 ? (
          <div className="account-api-keys-empty">
            <Key size={32} className="account-api-keys-empty-icon" />
            <p className="account-api-keys-empty-text">No API keys created yet</p>
          </div>
        ) : (
          <table className="account-api-keys-table">
            <thead>
              <tr className="account-api-keys-table-head-row">
                <th className="account-api-keys-table-head-cell">Name</th>
                <th className="account-api-keys-table-head-cell">Key</th>
                <th className="account-api-keys-table-head-cell">Created</th>
                <th className="account-api-keys-table-head-cell">Last Used</th>
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
                  </td>
                  <td className="account-api-keys-table-cell">
                    <div className="account-api-keys-key-row">
                      <code className="account-api-keys-key-code">
                        {showKey === apiKey.id
                          ? apiKey.key
                          : `${apiKey.key.substring(0, 8)}${'•'.repeat(16)}`}
                      </code>
                      <button
                        onClick={() =>
                          setShowKey(showKey === apiKey.id ? null : apiKey.id)
                        }
                        className="account-api-keys-icon-button"
                        aria-label={showKey === apiKey.id ? 'Hide key' : 'Show key'}
                      >
                        {showKey === apiKey.id ? (
                          <EyeOff size={14} />
                        ) : (
                          <Eye size={14} />
                        )}
                      </button>
                      <button
                        onClick={() => handleCopy(apiKey.key, apiKey.id)}
                        className="account-api-keys-icon-button"
                        aria-label="Copy key"
                      >
                        {copied === apiKey.id ? (
                          <Check size={14} className="account-api-keys-icon-button-copied" />
                        ) : (
                          <Copy size={14} />
                        )}
                      </button>
                    </div>
                  </td>
                  <td className="account-api-keys-table-cell account-api-keys-table-cell-meta">
                    {apiKey.createdAt.toLocaleDateString()}
                  </td>
                  <td className="account-api-keys-table-cell account-api-keys-table-cell-meta">
                    {apiKey.lastUsed
                      ? apiKey.lastUsed.toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td className="account-api-keys-table-cell account-api-keys-table-cell-actions">
                    <button
                      onClick={() => handleDelete(apiKey.id)}
                      className="account-api-keys-icon-button account-api-keys-icon-button-delete"
                      aria-label="Revoke key"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </AccountSectionCard>

      <div className="account-api-keys-usage">
        <h3 className="account-api-keys-usage-title">Using API Keys</h3>
        <p className="account-api-keys-usage-description">
          Include your API key in the Authorization header:
        </p>
        <code className="account-api-keys-usage-code">
          curl -H "Authorization: Bearer nx_your_api_key" \<br />
          &nbsp;&nbsp;https://api.nexus.naas.ai/v1/chat
        </code>
      </div>
    </div>
  );
}
