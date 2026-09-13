'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';
import { SectionsCoverFallback, SectionsCoverThumb } from './documents-cover-thumb';
import { DocumentsProjectOverflowMenu } from './documents-project-menu';
import {
  sectionsHomeTemplateCards,
  templatePreviewColors,
  templateSectionLabel,
  type DocumentsSeedTemplate,
} from '@/lib/documents-templates';
import type { DocumentsProject } from '@/stores/documents';

export function sectionsIndexHref(workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/documents/${encodeURIComponent(slug)}`;
}

export function SectionsIndexCard({
  project,
  workspaceId,
  templates,
  onOpen,
  onRename,
  onArchive,
}: {
  project: DocumentsProject;
  workspaceId: string;
  templates: DocumentsSeedTemplate[];
  onOpen: () => void;
  onRename?: (title: string) => void;
  onArchive?: () => void;
}) {
  const preview = templatePreviewColors(project.template_id, templates);
  const href = sectionsIndexHref(workspaceId, project.slug);
  const [showMenu, setShowMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [editValue, setEditValue] = useState(project.title);

  useEffect(() => {
    setEditValue(project.title);
  }, [project.title]);

  const submitRename = () => {
    const next = editValue.trim();
    if (next && next !== project.title) onRename?.(next);
    setRenaming(false);
  };

  return (
    <div
      data-testid="sections-index-card"
      data-slug={project.slug}
      className={`sections-overflow-host glass-card flex flex-col overflow-hidden transition-all hover:-translate-y-0.5 hover:border-workspace-accent/40 hover:shadow-md${showMenu ? ' is-menu-open' : ''}`}
      onContextMenu={(event) => {
        if (!onRename && !onArchive) return;
        event.preventDefault();
        setShowMenu(true);
      }}
    >
      <Link
        href={href}
        onClick={onOpen}
        className="flex cursor-pointer flex-col text-left no-underline focus:outline-none focus-visible:ring-2 focus-visible:ring-workspace-accent/40"
      >
        <SectionsCoverThumb
          workspaceId={workspaceId}
          slug={project.slug}
          title={project.title}
          preview={preview}
        />
      </Link>
      <div className="flex items-center gap-1 p-4">
        {renaming ? (
          <input
            type="text"
            value={editValue}
            onChange={(event) => setEditValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') submitRename();
              else if (event.key === 'Escape') setRenaming(false);
            }}
            onBlur={submitRename}
            autoFocus
            className="chat-rename-input"
            data-testid="sections-rename-input"
          />
        ) : (
          <Link
            href={href}
            onClick={onOpen}
            className="min-w-0 flex-1 no-underline"
          >
            <h3 className="truncate font-semibold leading-tight text-foreground">{project.title}</h3>
          </Link>
        )}
        {onRename && onArchive && !renaming ? (
          <DocumentsProjectOverflowMenu
            open={showMenu}
            onOpenChange={setShowMenu}
            onRename={() => {
              setEditValue(project.title);
              setRenaming(true);
            }}
            onArchive={onArchive}
          />
        ) : null}
      </div>
    </div>
  );
}

export function SectionsTemplateStrip({
  templates,
  creating,
  onSelect,
}: {
  templates: DocumentsSeedTemplate[];
  creating?: boolean;
  onSelect: (templateId: string) => void;
}) {
  const cards = sectionsHomeTemplateCards(templates);

  return (
    <section
      data-testid="sections-template-strip"
      className="border-b border-border bg-muted/50 px-6 py-5"
    >
      <h2 className="mb-4 text-sm font-medium text-foreground">Start a new document</h2>
      <div className="flex gap-4 overflow-x-auto pb-1">
        {cards.map((card) => {
          const seed = templates.find((row) => row.id === card.id);
          const first = seed?.sections?.[0];
          const coverTitle = first ? templateSectionLabel(first) : card.label;
          const preview = templatePreviewColors(card.id, templates);
          return (
            <button
              key={card.id}
              type="button"
              data-testid="sections-template-card"
              data-template-id={card.id}
              disabled={creating}
              onClick={() => onSelect(card.id)}
              className="w-[10.5rem] flex-shrink-0 text-left disabled:cursor-default disabled:opacity-50"
            >
              <div className="relative aspect-[8.5/11] w-full overflow-hidden rounded-sm border border-border bg-background shadow-sm transition-shadow hover:shadow-md">
                {card.blank ? (
                  <div
                    className="absolute inset-0 flex items-center justify-center bg-white"
                    data-testid="sections-template-blank-thumb"
                  >
                    <Plus size={28} className="text-workspace-accent" strokeWidth={2.25} />
                  </div>
                ) : (
                  <SectionsCoverFallback title={coverTitle} preview={preview} />
                )}
              </div>
              <span className="mt-2 block truncate text-xs text-foreground">{card.label}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function DocumentsIndexGallery({
  projects,
  workspaceId,
  templates,
  onOpen,
  onRename,
  onArchive,
}: {
  projects: DocumentsProject[];
  workspaceId: string;
  templates: DocumentsSeedTemplate[];
  onOpen: (project: DocumentsProject) => void;
  onRename?: (project: DocumentsProject, title: string) => void;
  onArchive?: (project: DocumentsProject) => void;
}) {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
      data-testid="documents-index-gallery"
    >
      {projects.map((project) => (
        <SectionsIndexCard
          key={project.slug}
          project={project}
          workspaceId={workspaceId}
          templates={templates}
          onOpen={() => onOpen(project)}
          onRename={onRename ? (title) => onRename(project, title) : undefined}
          onArchive={onArchive ? () => onArchive(project) : undefined}
        />
      ))}
    </div>
  );
}
