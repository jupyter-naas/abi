'use client';

import { Header } from '@/components/shell/header';
import { ExternalLink, Headphones, BookOpen } from 'lucide-react';

export default function HelpPage() {
  return (
    <div className="flex h-full flex-col">
      <Header title="Help" subtitle="Get support and documentation" />
      <div className="flex flex-1 items-center justify-center p-8">
      <div className="flex flex-col items-center gap-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">Need Help?</h1>
          <p className="mt-2 text-muted-foreground">
            Choose an option below to get support
          </p>
        </div>

        <div className="flex gap-4">
          <a
            href="https://naas.ai/contact"
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-44 flex-col items-center gap-3 rounded-lg border border-border bg-card p-6 transition-all hover:border-workspace-accent hover:shadow-md"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-workspace-accent-10">
              <Headphones size={24} className="text-workspace-accent" />
            </div>
            <span className="font-medium">Call Support</span>
            <ExternalLink size={14} className="text-muted-foreground" />
          </a>

          <a
            href="https://docs.naas.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-44 flex-col items-center gap-3 rounded-lg border border-border bg-card p-6 transition-all hover:border-workspace-accent hover:shadow-md"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-workspace-accent-10">
              <BookOpen size={24} className="text-workspace-accent" />
            </div>
            <span className="font-medium">Read the Docs</span>
            <ExternalLink size={14} className="text-muted-foreground" />
          </a>
        </div>
      </div>
      </div>
    </div>
  );
}
