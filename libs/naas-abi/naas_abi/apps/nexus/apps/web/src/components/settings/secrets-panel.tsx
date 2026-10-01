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
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useConfirm } from '@/components/ui/dialogs';
import { Input, Select, Textarea } from '@/components/ui/input';
import {
  SettingsEmpty,
  SettingsField,
  SettingsLoading,
  SettingsNotice,
  SettingsPageHeader,
  SettingsSection,
  settingsTable,
} from '@/components/settings/settings-ui';
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
  const [importNotice, setImportNotice] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);
  const { confirm: confirmDelete, dialog: confirmDialog } = useConfirm();
  
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

  const handleDelete = async (id: string) => {
    const ok = await confirmDelete({
      title: 'Delete secret?',
      description: 'Are you sure you want to delete this secret?',
      confirmLabel: 'Delete',
    });
    if (ok) deleteSecret(id);
  };

  const handleImport = () => {
    if (!importContent.trim()) return;
    if (!currentWorkspaceId) return;
    importFromEnv(currentWorkspaceId, importContent);
    setImportContent('');
    setShowImportModal(false);
  };

  const handleLoadFromRootEnv = async () => {
    setImportNotice(null);
    try {
      const authModule = await import('@/stores/auth');
      const { authFetch, useAuthStore } = authModule;
      
      // Check if we have a token
      const currentToken = useAuthStore.getState().token;
      if (!currentToken) {
        window.location.href = '/auth/login';
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
      setImportNotice({
        tone: 'success',
        text: `Loaded ${data.env_content.split('\n').filter((l: string) => l.trim() && !l.startsWith('#')).length} keys from ${data.path}. Click "Import" to save them to the database.`,
      });
    } catch (error) {
      console.error('Failed to load root .env:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setImportNotice({
        tone: 'error',
        text: `Failed to load .env file: ${errorMsg}. ${errorMsg.includes('401') || errorMsg.includes('authenticated') ? 'Try logging out and back in.' : 'Make sure you have access to this workspace.'}`,
      });
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
    return <SettingsLoading label="Loading secrets…" />;
  }

  const closeImport = () => {
    setShowImportModal(false);
    setImportNotice(null);
  };

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title={
          <span className="flex items-center gap-2">
            Secrets
            <Badge>{secrets.length}</Badge>
          </span>
        }
        description="Manage API keys, tokens, and credentials"
        actions={
          <>
            <Button variant="secondary" onClick={() => setShowImportModal(true)}>
              <Upload size={16} />
              Import
            </Button>
            <Button variant="secondary" onClick={handleExport} disabled={secrets.length === 0}>
              <Download size={16} />
              Export
            </Button>
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} />
              Add Secret
            </Button>
          </>
        }
      />

      {showImportModal && mounted && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg border border-border bg-background p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold">Import from .env</h3>
              <Button variant="ghost" size="icon" onClick={closeImport} title="Close">
                <X size={18} />
              </Button>
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              Paste your .env file contents below. Existing keys will be updated, new keys will be added.
            </p>
            <div className="mb-4">
              <Button variant="secondary" size="sm" onClick={handleLoadFromRootEnv}>
                <FileKey size={14} />
                Load from root .env
              </Button>
            </div>
            {importNotice && (
              <SettingsNotice tone={importNotice.tone} className="mb-4">
                {importNotice.text}
              </SettingsNotice>
            )}
            <Textarea
              value={importContent}
              onChange={(e) => setImportContent(e.target.value)}
              placeholder="OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgres://..."
              rows={10}
              className="mb-4 resize-none font-mono"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={closeImport}>
                Cancel
              </Button>
              <Button onClick={handleImport} disabled={!importContent.trim()}>
                Import
              </Button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {showAddForm && (
        <SettingsSection title="Add New Secret">
          <div className="grid gap-4">
            <div className="grid grid-cols-2 gap-4">
              <SettingsField label="Key Name *">
                <Input
                  type="text"
                  value={newSecret.key}
                  onChange={(e) => setNewSecret({ ...newSecret, key: e.target.value })}
                  placeholder="e.g., OPENAI_API_KEY"
                  className="font-mono"
                />
              </SettingsField>
              <SettingsField label="Category">
                <Select
                  value={newSecret.category}
                  onChange={(e) => setNewSecret({ ...newSecret, category: e.target.value as Secret['category'] })}
                >
                  {categoryOptions.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </SettingsField>
            </div>
            <SettingsField label="Value *">
              <Input
                type="password"
                value={newSecret.value}
                onChange={(e) => setNewSecret({ ...newSecret, value: e.target.value })}
                placeholder="Enter secret value"
                className="font-mono"
              />
            </SettingsField>
            <SettingsField label="Description">
              <Input
                type="text"
                value={newSecret.description}
                onChange={(e) => setNewSecret({ ...newSecret, description: e.target.value })}
                placeholder="Optional description"
              />
            </SettingsField>
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setShowAddForm(false);
                  setNewSecret({ key: '', value: '', description: '', category: 'api_keys' });
                }}
              >
                Cancel
              </Button>
              <Button onClick={handleAdd} disabled={!newSecret.key.trim() || !newSecret.value}>
                Add Secret
              </Button>
            </div>
          </div>
        </SettingsSection>
      )}

      {secrets.length === 0 ? (
        <SettingsEmpty
          icon={<Key size={40} className="opacity-40" />}
          title="No secrets configured"
          description="Add API keys and credentials to use with your models and integrations"
          action={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setShowImportModal(true)}>
                <Upload size={16} />
                Import .env
              </Button>
              <Button onClick={() => setShowAddForm(true)}>
                <Plus size={16} />
                Add Secret
              </Button>
            </div>
          }
        />
      ) : (
        <div className="space-y-6">
          {Object.entries(secretsByCategory).map(([category, categorySecrets]) => {
            const CategoryIcon = categoryIcons[category as Secret['category']] || Key;

            return (
              <div key={category} className="space-y-3">
                <div className="flex items-center gap-2">
                  <CategoryIcon size={16} className="text-muted-foreground" />
                  <h3 className="text-sm font-medium text-muted-foreground">
                    {categoryLabels[category as Secret['category']] || category}
                  </h3>
                  <Badge>{categorySecrets.length}</Badge>
                </div>

                <div className={settingsTable.wrapper}>
                  <table className={settingsTable.table}>
                    <thead>
                      <tr className={settingsTable.headRow}>
                        <th className={settingsTable.th}>Key</th>
                        <th className={settingsTable.th}>Value</th>
                        <th className={settingsTable.th}>Description</th>
                        <th className={cn(settingsTable.th, 'w-24')}>
                          <span className="sr-only">Actions</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {categorySecrets.map((secret) => {
                        const isCopied = copiedId === secret.id;

                        return (
                          <tr key={secret.id} className={settingsTable.row}>
                            <td className={settingsTable.td}>
                              <code className="bg-muted px-2 py-1 font-mono text-xs">{secret.key}</code>
                            </td>
                            <td className={settingsTable.td}>
                              <div className="flex items-center gap-2">
                                <code className="bg-muted px-2 py-1 font-mono text-xs text-muted-foreground">
                                  {secret.masked_value}
                                </code>
                                <span className="text-xs text-muted-foreground">(encrypted)</span>
                              </div>
                            </td>
                            <td className={cn(settingsTable.td, 'text-muted-foreground')}>
                              {secret.description || '—'}
                            </td>
                            <td className={settingsTable.td}>
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => copyToClipboard(secret.id, secret.key)}
                                  title="Copy secret key"
                                >
                                  {isCopied ? <Check size={14} className="text-primary" /> : <Copy size={14} />}
                                </Button>
                                <Button
                                  variant="destructive-ghost"
                                  size="icon"
                                  onClick={() => void handleDelete(secret.id)}
                                  title="Delete"
                                >
                                  <Trash2 size={14} />
                                </Button>
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

      <SettingsNotice tone="warning" icon={<Shield size={14} />}>
        <p className="font-medium">Security Notice</p>
        <p>
          Secrets are stored locally in your browser. For production use, consider using a secure secrets manager.
          Never share or expose these values publicly.
        </p>
      </SettingsNotice>
      {confirmDialog}
    </div>
  );
}
