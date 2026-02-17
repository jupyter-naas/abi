'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Key,
  Plus,
  Trash2,
  Upload,
  Download,
  Copy,
  Check,
  X,
  Shield,
  Lock,
  KeyRound,
  FileKey,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSecretsStore, type Secret } from '@/stores/secrets';
import { useWorkspaceStore } from '@/stores/workspace';

const categoryIcons: Record<Secret['category'], React.ElementType> = {
  api_keys: Key,
  credentials: Lock,
  tokens: KeyRound,
  other: FileKey,
};

const categoryLabels: Record<Secret['category'], string> = {
  api_keys: 'API Keys',
  credentials: 'Credentials',
  tokens: 'Tokens',
  other: 'Other',
};

const categoryOptions: { id: Secret['category']; label: string }[] = [
  { id: 'api_keys', label: 'API Key' },
  { id: 'credentials', label: 'Credential' },
  { id: 'tokens', label: 'Token' },
  { id: 'other', label: 'Other' },
];

export function SecretsPanel() {
  const { secrets, addSecret, updateSecret, deleteSecret, importFromEnv, exportToEnv, fetchSecrets } = useSecretsStore();
  const currentWorkspaceId = useWorkspaceStore((state) => state.currentWorkspaceId);
  
  const [mounted, setMounted] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importContent, setImportContent] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  
  // New secret form
  const [newSecret, setNewSecret] = useState({
    key: '',
    value: '',
    description: '',
    category: 'api_keys' as Secret['category'],
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  // Load secrets when workspace changes
  useEffect(() => {
    if (currentWorkspaceId) {
      fetchSecrets(currentWorkspaceId);
    }
  }, [currentWorkspaceId, fetchSecrets]);

  const copyToClipboard = async (id: string, value: string) => {
    await navigator.clipboard.writeText(value);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleAdd = () => {
    if (!newSecret.key.trim()) return;
    
    addSecret(
      currentWorkspaceId || '', 
      newSecret.key.trim().toUpperCase().replace(/\s+/g, '_'),
      newSecret.value,
      newSecret.description.trim(),
      newSecret.category
    );
    
    setNewSecret({ key: '', value: '', description: '', category: 'api_keys' });
    setShowAddForm(false);
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this secret?')) {
      deleteSecret(id);
    }
  };

  const handleImport = () => {
    if (!importContent.trim()) return;
    if (!currentWorkspaceId) return;
    importFromEnv(currentWorkspaceId, importContent);
    setImportContent('');
    setShowImportModal(false);
  };

  const handleLoadFromRootEnv = async () => {
    try {
      const authModule = await import('@/stores/auth');
      const { authFetch, useAuthStore } = authModule;
      
      // Check if we have a token
      const currentToken = useAuthStore.getState().token;
      if (!currentToken) {
        alert('You need to log in first to import secrets.');
        window.location.href = '/login';
        return;
      }
      
      const response = await authFetch('/api/admin/root-env');
      
      if (!response.ok) {
        const errorText = await response.text();
        let errorMsg = 'Unknown error';
        try {
          const errorJson = JSON.parse(errorText);
          errorMsg = errorJson.detail || errorJson.message || 'Unknown error';
        } catch {
          errorMsg = errorText || response.statusText;
        }
        throw new Error(errorMsg);
      }
      
      const data = await response.json();
      setImportContent(data.env_content);
      
      // Show success feedback
      alert(`✅ Loaded ${data.env_content.split('\n').filter((l: string) => l.trim() && !l.startsWith('#')).length} keys from:\n${data.path}\n\nClick "Import" to save them to the database.`);
    } catch (error) {
      console.error('Failed to load root .env:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      alert(`❌ Failed to load .env file:\n\n${errorMsg}\n\n${errorMsg.includes('401') || errorMsg.includes('authenticated') ? 'Try logging out and back in.' : 'Make sure you have access to this workspace.'}`);
    }
  };

  const handleExport = () => {
    const content = exportToEnv();
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.env.nexus';
    a.click();
    URL.revokeObjectURL(url);
  };

  const maskValue = (value: string) => {
    if (value.length <= 8) return '••••••••';
    return value.slice(0, 4) + '••••••••' + value.slice(-4);
  };

  // Group secrets by category
  const secretsByCategory = mounted
    ? secrets.reduce((acc, secret) => {
        if (!acc[secret.category]) {
          acc[secret.category] = [];
        }
        acc[secret.category].push(secret);
        return acc;
      }, {} as Record<string, Secret[]>)
    : {};

  if (!mounted) {
    return (
      <div className="flex items-center justify-center p-8">
        <p className="text-muted-foreground">Loading secrets...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Secrets</h2>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
              {secrets.length}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Manage API keys, tokens, and credentials
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowImportModal(true)}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
          >
            <Upload size={16} />
            Import
          </button>
          <button
            onClick={handleExport}
            disabled={secrets.length === 0}
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={16} />
            Export
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus size={16} />
            Add Secret
          </button>
        </div>
      </div>

      {/* Import Modal */}
      {showImportModal && mounted && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-lg border bg-background p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold">Import from .env</h3>
              <button
                onClick={() => setShowImportModal(false)}
                className="rounded p-1 hover:bg-muted"
              >
                <X size={20} />
              </button>
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              Paste your .env file contents below. Existing keys will be updated, new keys will be added.
            </p>
            <div className="mb-4 flex gap-2">
              <button
                onClick={handleLoadFromRootEnv}
                className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
              >
                <FileKey size={14} />
                Load from root .env
              </button>
            </div>
            <textarea
              value={importContent}
              onChange={(e) => setImportContent(e.target.value)}
              placeholder="OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgres://..."
              rows={10}
              className="mb-4 w-full resize-none rounded-lg border bg-background px-4 py-3 font-mono text-sm outline-none focus:ring-2 focus:ring-primary/30"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowImportModal(false)}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleImport}
                disabled={!importContent.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Import
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Add Form */}
      {showAddForm && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <h3 className="mb-4 font-medium">Add New Secret</h3>
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Key Name *</label>
                <input
                  type="text"
                  value={newSecret.key}
                  onChange={(e) => setNewSecret({ ...newSecret, key: e.target.value })}
                  placeholder="e.g., OPENAI_API_KEY"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Category</label>
                <select
                  value={newSecret.category}
                  onChange={(e) => setNewSecret({ ...newSecret, category: e.target.value as Secret['category'] })}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {categoryOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Value *</label>
              <input
                type="password"
                value={newSecret.value}
                onChange={(e) => setNewSecret({ ...newSecret, value: e.target.value })}
                placeholder="Enter secret value"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm font-mono outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Description</label>
              <input
                type="text"
                value={newSecret.description}
                onChange={(e) => setNewSecret({ ...newSecret, description: e.target.value })}
                placeholder="Optional description"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setNewSecret({ key: '', value: '', description: '', category: 'api_keys' });
                }}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={!newSecret.key.trim() || !newSecret.value}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Add Secret
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Secrets List */}
      {secrets.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
          <Key size={48} className="mb-4 text-muted-foreground/30" />
          <h3 className="mb-2 font-medium">No secrets configured</h3>
          <p className="mb-4 text-sm text-muted-foreground">
            Add API keys and credentials to use with your models and integrations
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setShowImportModal(true)}
              className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm hover:bg-muted"
            >
              <Upload size={16} />
              Import .env
            </button>
            <button
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus size={16} />
              Add Secret
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(secretsByCategory).map(([category, categorySecrets]) => {
            const CategoryIcon = categoryIcons[category as Secret['category']] || Key;
            
            return (
              <div key={category}>
                <div className="mb-3 flex items-center gap-2">
                  <CategoryIcon size={16} className="text-muted-foreground" />
                  <h3 className="text-sm font-medium text-muted-foreground">
                    {categoryLabels[category as Secret['category']] || category}
                  </h3>
                  <span className="text-xs text-muted-foreground">({categorySecrets.length})</span>
                </div>
                
                <div className="rounded-lg border overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50 text-left text-sm">
                        <th className="p-3 font-medium">Key</th>
                        <th className="p-3 font-medium">Value</th>
                        <th className="p-3 font-medium">Description</th>
                        <th className="p-3 w-32"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {categorySecrets.map((secret) => {
                        const isCopied = copiedId === secret.id;
                        
                        return (
                          <tr key={secret.id} className="border-b last:border-0">
                            <td className="p-3">
                              <code className="rounded bg-secondary px-2 py-1 text-xs font-mono">
                                {secret.key}
                              </code>
                            </td>
                            <td className="p-3">
                              <div className="flex items-center gap-2">
                                <code className="rounded bg-secondary px-2 py-1 text-xs font-mono text-muted-foreground">
                                  {secret.masked_value}
                                </code>
                                <span className="text-xs text-muted-foreground">(encrypted)</span>
                              </div>
                            </td>
                            <td className="p-3 text-sm text-muted-foreground">
                              {secret.description || '—'}
                            </td>
                            <td className="p-3">
                              <div className="flex items-center justify-end gap-1">
                                <button
                                  onClick={() => copyToClipboard(secret.id, secret.key)}
                                  className="rounded p-1.5 hover:bg-muted"
                                  title="Copy secret key"
                                >
                                  {isCopied ? (
                                    <Check size={14} className="text-green-500" />
                                  ) : (
                                    <Copy size={14} />
                                  )}
                                </button>
                                <button
                                  onClick={() => handleDelete(secret.id)}
                                  className="rounded p-1.5 text-muted-foreground hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
                                  title="Delete"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Security Notice */}
      <div className="flex items-start gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-4 dark:border-yellow-900 dark:bg-yellow-950/30">
        <Shield size={20} className="mt-0.5 flex-shrink-0 text-yellow-600 dark:text-yellow-500" />
        <div className="text-sm">
          <p className="font-medium text-yellow-800 dark:text-yellow-200">Security Notice</p>
          <p className="text-yellow-700 dark:text-yellow-300">
            Secrets are stored locally in your browser. For production use, consider using a secure secrets manager.
            Never share or expose these values publicly.
          </p>
        </div>
      </div>
    </div>
  );
}
