'use client';

import { useState } from 'react';
import { Download, FileJson, FileText, Database, Clock, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SettingsNotice, SettingsPageHeader, SettingsSection } from '@/components/settings/settings-ui';

interface ExportJob {
  id: string;
  type: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  createdAt: Date;
  downloadUrl?: string;
}

export default function ExportPage() {
  const [exports, setExports] = useState<ExportJob[]>([]);
  const [exporting, setExporting] = useState<string | null>(null);

  const handleExport = (type: string) => {
    setExporting(type);
    
    // Simulate export
    setTimeout(() => {
      const newExport: ExportJob = {
        id: Math.random().toString(36).substring(2),
        type,
        status: 'completed',
        createdAt: new Date(),
        downloadUrl: '#',
      };
      setExports([newExport, ...exports]);
      setExporting(null);
    }, 2000);
  };

  const exportOptions = [
    {
      id: 'conversations',
      name: 'Conversations',
      description: 'Export all chat conversations and messages',
      icon: FileText,
      format: 'JSON',
    },
    {
      id: 'ontology',
      name: 'Ontology',
      description: 'Export your ontology definitions',
      icon: Database,
      format: 'YAML / RDF',
    },
    {
      id: 'graph',
      name: 'Knowledge Graph',
      description: 'Export all graph nodes and relationships',
      icon: Database,
      format: 'JSON-LD',
    },
    {
      id: 'all',
      name: 'Full Backup',
      description: 'Export everything in your workspace',
      icon: FileJson,
      format: 'ZIP',
    },
  ];

  return (
    <div className="space-y-6">
      <SettingsPageHeader title="Data Export" description="Download your data from NEXUS" />

      <div className="grid gap-4 sm:grid-cols-2">
        {exportOptions.map((option) => {
          const Icon = option.icon;
          const isExporting = exporting === option.id;

          return (
            <SettingsSection key={option.id}>
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center bg-muted text-muted-foreground">
                  <Icon size={20} />
                </div>
                <div>
                  <h3 className="font-medium">{option.name}</h3>
                  <p className="text-xs text-muted-foreground">{option.format}</p>
                </div>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">{option.description}</p>
              <Button onClick={() => handleExport(option.id)} disabled={isExporting} className="w-full">
                {isExporting ? (
                  <>
                    <Clock size={16} className="animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download size={16} />
                    Export
                  </>
                )}
              </Button>
            </SettingsSection>
          );
        })}
      </div>

      <SettingsSection title="Export History">
        {exports.length === 0 ? (
          <p className="text-sm text-muted-foreground">No exports yet. Your export history will appear here.</p>
        ) : (
          <div className="space-y-3">
            {exports.map((exp) => (
              <div key={exp.id} className="flex items-center justify-between border border-border bg-muted/30 p-3">
                <div className="flex items-center gap-3">
                  <CheckCircle size={18} className="text-primary" />
                  <div>
                    <p className="text-sm font-medium capitalize">{exp.type}</p>
                    <p className="text-xs text-muted-foreground">{exp.createdAt.toLocaleString()}</p>
                  </div>
                </div>
                <Button variant="secondary" size="sm">
                  <Download size={14} />
                  Download
                </Button>
              </div>
            ))}
          </div>
        )}
      </SettingsSection>

      <SettingsNotice tone="warning">
        <strong>Data Retention:</strong> Exports are available for download for 7 days. After that, you&apos;ll need
        to create a new export.
      </SettingsNotice>
    </div>
  );
}
