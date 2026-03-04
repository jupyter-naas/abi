'use client';

import { useState, useEffect } from 'react';
import { Save, RotateCcw, Check, AlertCircle } from 'lucide-react';
import { useIntegrationsStore, type ProviderConfig } from '@/stores/integrations';

// Simple YAML serializer (for display purposes)
function providersToYaml(providers: ProviderConfig[]): string {
  let yaml = '# NEXUS Models Configuration\n';
  yaml += '# Edit this file to configure your AI models\n\n';
  yaml += 'providers:\n';

  for (const p of providers) {
    yaml += `  - id: ${p.id}\n`;
    yaml += `    name: "${p.name}"\n`;
    yaml += `    type: ${p.type}\n`;
    yaml += `    enabled: ${p.enabled}\n`;
    yaml += `    model: ${p.model}\n`;
    if (p.endpoint) {
      yaml += `    endpoint: ${p.endpoint}\n`;
    }
    if (p.apiKey) {
      yaml += `    apiKey: "${p.apiKey.slice(0, 8)}..." # hidden\n`;
    }
    yaml += '\n';
  }

  return yaml;
}

// Simple YAML parser (basic, for demo)
function yamlToProviders(yaml: string): ProviderConfig[] | null {
  try {
    // This is a simplified parser - in production, use a proper YAML library
    const providers: ProviderConfig[] = [];
    const lines = yaml.split('\n');
    let currentProvider: Partial<ProviderConfig> | null = null;

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('#') || trimmed === '') continue;

      if (trimmed.startsWith('- id:')) {
        if (currentProvider && currentProvider.id) {
          providers.push(currentProvider as ProviderConfig);
        }
        currentProvider = {
          id: trimmed.replace('- id:', '').trim(),
          createdAt: new Date(),
          updatedAt: new Date(),
        };
      } else if (currentProvider) {
        const match = trimmed.match(/^(\w+):\s*(.+)$/);
        if (match) {
          const [, key, value] = match;
          const cleanValue = value.replace(/^["']|["']$/g, '').replace(/\s*#.*$/, '');
          
          if (key === 'enabled') {
            (currentProvider as any)[key] = cleanValue === 'true';
          } else if (key !== 'apiKey' || !cleanValue.includes('...')) {
            (currentProvider as any)[key] = cleanValue;
          }
        }
      }
    }

    if (currentProvider && currentProvider.id) {
      providers.push(currentProvider as ProviderConfig);
    }

    return providers;
  } catch {
    return null;
  }
}

export function YamlEditor() {
  const { providers } = useIntegrationsStore();
  const [content, setContent] = useState('');
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setContent(providersToYaml(providers));
  }, [providers]);

  const handleSave = () => {
    const parsed = yamlToProviders(content);
    if (parsed) {
      // In a real implementation, we'd update the store here
      setSaved(true);
      setError(null);
      setTimeout(() => setSaved(false), 2000);
    } else {
      setError('Invalid YAML format');
    }
  };

  const handleReset = () => {
    setContent(providersToYaml(providers));
    setError(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Edit provider configuration as YAML. For full editing, use the Lab module.
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-secondary"
          >
            <RotateCcw size={14} />
            Reset
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {saved ? <Check size={14} /> : <Save size={14} />}
            {saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="rounded-xl border bg-zinc-900 p-4">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="h-96 w-full resize-none bg-transparent font-mono text-sm text-zinc-100 outline-none"
          spellCheck={false}
        />
      </div>

      <p className="text-xs text-muted-foreground">
        Note: API keys are partially hidden for security. Edit individual models in table view to update keys.
      </p>
    </div>
  );
}
