'use client';

import { useState } from 'react';
import { Download, FileJson, FileText, Database, Clock, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">Data Export</h2>
        <p className="text-sm text-muted-foreground">
          Download your data from NEXUS
        </p>
      </div>

      {/* Export options */}
      <div className="grid gap-4 sm:grid-cols-2">
        {exportOptions.map((option) => {
          const Icon = option.icon;
          const isExporting = exporting === option.id;
          
          return (
            <div key={option.id} className="rounded-xl border bg-card p-6">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
                  <Icon size={20} />
                </div>
                <div>
                  <h3 className="font-medium">{option.name}</h3>
                  <p className="text-xs text-muted-foreground">
                    {option.format}
                  </p>
                </div>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                {option.description}
              </p>
              <button
                onClick={() => handleExport(option.id)}
                disabled={isExporting}
                className={cn(
                  'flex w-full items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-colors',
                  isExporting
                    ? 'bg-secondary text-muted-foreground'
                    : 'bg-primary text-primary-foreground hover:bg-primary/90'
                )}
              >
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
              </button>
            </div>
          );
        })}
      </div>

      {/* Export history */}
      <div className="rounded-xl border bg-card p-6">
        <h3 className="mb-4 font-semibold">Export History</h3>
        {exports.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No exports yet. Your export history will appear here.
          </p>
        ) : (
          <div className="space-y-3">
            {exports.map((exp) => (
              <div
                key={exp.id}
                className="flex items-center justify-between rounded-lg border bg-secondary/30 p-3"
              >
                <div className="flex items-center gap-3">
                  <CheckCircle size={18} className="text-primary" />
                  <div>
                    <p className="text-sm font-medium capitalize">{exp.type}</p>
                    <p className="text-xs text-muted-foreground">
                      {exp.createdAt.toLocaleString()}
                    </p>
                  </div>
                </div>
                <button className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-sm hover:bg-secondary">
                  <Download size={14} />
                  Download
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Data retention notice */}
      <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4">
        <p className="text-sm text-yellow-600 dark:text-yellow-400">
          <strong>Data Retention:</strong> Exports are available for download for
          7 days. After that, you'll need to create a new export.
        </p>
      </div>
    </div>
  );
}
