'use client';

import { Header } from '@/components/shell/header';
import {
  FileText,
  Presentation,
  Table,
  Trello,
  Calendar,
  Plus,
  ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface AppCardProps {
  icon: React.ReactNode;
  name: string;
  description: string;
  status: 'available' | 'coming-soon';
}

function AppCard({ icon, name, description, status }: AppCardProps) {
  return (
    <div
      className={cn(
        'group relative flex flex-col rounded-xl border bg-card p-6 transition-all',
        status === 'available' && 'cursor-pointer hover:border-workspace-accent hover:shadow-md',
        status === 'coming-soon' && 'opacity-60'
      )}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-workspace-accent-10 text-workspace-accent">
        {icon}
      </div>
      <h3 className="mb-1 font-semibold">{name}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
      {status === 'coming-soon' && (
        <span className="mt-3 inline-flex w-fit rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          Coming Soon
        </span>
      )}
      {status === 'available' && (
        <ExternalLink
          size={16}
          className="absolute right-4 top-4 opacity-0 transition-opacity group-hover:opacity-100"
        />
      )}
    </div>
  );
}

const apps: AppCardProps[] = [
  {
    icon: <FileText size={24} />,
    name: 'Docs',
    description: 'Rich text editor for documentation and notes',
    status: 'coming-soon',
  },
  {
    icon: <Presentation size={24} />,
    name: 'Slides',
    description: 'Create presentations with agent assistance',
    status: 'coming-soon',
  },
  {
    icon: <Table size={24} />,
    name: 'Spreadsheets',
    description: 'Data tables with formula support',
    status: 'coming-soon',
  },
  {
    icon: <Trello size={24} />,
    name: 'Board',
    description: 'Kanban boards and whiteboards',
    status: 'coming-soon',
  },
  {
    icon: <Calendar size={24} />,
    name: 'Calendar',
    description: 'Schedule and timeline management',
    status: 'coming-soon',
  },
];

export default function AppsPage() {
  return (
    <div className="flex h-full flex-col">
      <Header title="Apps" subtitle="Extensible applications for your workspace" />

      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-5xl">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">Installed Apps</h2>
              <p className="text-muted-foreground">
                Apps extend NEXUS with specialized functionality
              </p>
            </div>
            <button
              className={cn(
                'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                'hover:opacity-90'
              )}
            >
              <Plus size={16} />
              Browse Marketplace
            </button>
          </div>

          {/* Apps grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {apps.map((app) => (
              <AppCard key={app.name} {...app} />
            ))}
          </div>

          {/* Framework info */}
          <div className="mt-12 rounded-xl border bg-muted/30 p-6">
            <h3 className="mb-2 font-semibold">App Framework</h3>
            <p className="mb-4 text-sm text-muted-foreground">
              NEXUS supports custom apps as first-class citizens. Apps share identity, permissions,
              search, and ABI access through a unified API.
            </p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>• App registration system</li>
              <li>• Shared identity & permissions</li>
              <li>• Shared search & context</li>
              <li>• ABI access via API</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
