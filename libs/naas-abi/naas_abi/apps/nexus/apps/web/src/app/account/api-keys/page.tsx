'use client';

import { useState } from 'react';
import { Plus, Copy, Trash2, Eye, EyeOff, Key, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">API Keys</h2>
          <p className="text-sm text-muted-foreground">
            Manage API keys for programmatic access to NEXUS
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
        >
          <Plus size={16} />
          Create Key
        </button>
      </div>

      {/* Create new key form */}
      {showCreate && (
        <div className="rounded-xl border bg-card p-4">
          <h3 className="mb-4 font-medium">Create New API Key</h3>
          <div className="flex gap-3">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g., Production, CI/CD)"
              className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500/30"
            />
            <button
              onClick={handleCreate}
              className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="rounded-lg border px-4 py-2 text-sm text-muted-foreground hover:bg-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Keys list */}
      <div className="rounded-xl border bg-card">
        {keys.length === 0 ? (
          <div className="flex flex-col items-center py-12 text-center">
            <Key size={32} className="mb-3 text-muted-foreground" />
            <p className="text-muted-foreground">No API keys created yet</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b text-left text-sm text-muted-foreground">
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Key</th>
                <th className="p-4 font-medium">Created</th>
                <th className="p-4 font-medium">Last Used</th>
                <th className="p-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((apiKey) => (
                <tr key={apiKey.id} className="border-b last:border-0">
                  <td className="p-4 font-medium">{apiKey.name}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <code className="rounded bg-secondary px-2 py-1 text-xs">
                        {showKey === apiKey.id
                          ? apiKey.key
                          : `${apiKey.key.substring(0, 8)}${'•'.repeat(16)}`}
                      </code>
                      <button
                        onClick={() =>
                          setShowKey(showKey === apiKey.id ? null : apiKey.id)
                        }
                        className="text-muted-foreground hover:text-foreground"
                      >
                        {showKey === apiKey.id ? (
                          <EyeOff size={14} />
                        ) : (
                          <Eye size={14} />
                        )}
                      </button>
                      <button
                        onClick={() => handleCopy(apiKey.key, apiKey.id)}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        {copied === apiKey.id ? (
                          <Check size={14} className="text-blue-500" />
                        ) : (
                          <Copy size={14} />
                        )}
                      </button>
                    </div>
                  </td>
                  <td className="p-4 text-sm text-muted-foreground">
                    {apiKey.createdAt.toLocaleDateString()}
                  </td>
                  <td className="p-4 text-sm text-muted-foreground">
                    {apiKey.lastUsed
                      ? apiKey.lastUsed.toLocaleDateString()
                      : 'Never'}
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={() => handleDelete(apiKey.id)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Usage info */}
      <div className="rounded-xl border bg-muted/30 p-4">
        <h3 className="mb-2 font-medium">Using API Keys</h3>
        <p className="mb-3 text-sm text-muted-foreground">
          Include your API key in the Authorization header:
        </p>
        <code className="block rounded-lg bg-zinc-900 p-3 text-xs text-zinc-100">
          curl -H "Authorization: Bearer nx_your_api_key" \<br />
          &nbsp;&nbsp;https://api.nexus.naas.ai/v1/chat
        </code>
      </div>
    </div>
  );
}
