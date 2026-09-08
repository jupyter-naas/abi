'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';
import { SlidesCoverFallback, SlidesCoverThumb } from './slides-cover-thumb';
import { SlidesProjectOverflowMenu } from './slides-project-menu';
import {
  slidesHomeTemplateCards,
  templatePreviewColors,
  templateSlideLabel,
  type SlidesSeedTemplate,
} from '@/lib/slides-templates';
import type { SlidesProject } from '@/stores/slides';

export function slidesIndexHref(workspaceId: string, slug: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/slides/${encodeURIComponent(slug)}`;
}

export function SlidesIndexCard({
  project,
  workspaceId,
  templates,
  onOpen,
  onRename,
  onArchive,
}: {
  project: SlidesProject;
  workspaceId: string;
  templates: SlidesSeedTemplate[];
  onOpen: () => void;
  onRename?: (title: string) => void;
  onArchive?: () => void;
}) {
  const preview = templatePreviewColors(project.template_id, templates);
  const href = slidesIndexHref(workspaceId, project.slug);
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
      data-testid="slides-index-card"
      data-slug={project.slug}
      className={`slides-overflow-host glass-card flex flex-col overflow-hidden transition-all hover:-translate-y-0.5 hover:border-workspace-accent/40 hover:shadow-md${showMenu ? ' is-menu-open' : ''}`}
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
        <SlidesCoverThumb
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
            data-testid="slides-rename-input"
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
          <SlidesProjectOverflowMenu
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

export function SlidesTemplateStrip({
  templates,
  creating,
  onSelect,
}: {
  templates: SlidesSeedTemplate[];
  creating?: boolean;
  onSelect: (templateId: string) => void;
}) {
  const cards = slidesHomeTemplateCards(templates);

  return (
    <section
      data-testid="slides-template-strip"
      className="border-b border-border bg-muted/50 px-6 py-5"
    >
      <h2 className="mb-4 text-sm font-medium text-foreground">Start a new presentation</h2>
      <div className="flex gap-4 overflow-x-auto pb-1">
        {cards.map((card) => {
          const seed = templates.find((row) => row.id === card.id);
          const first = seed?.slides?.[0];
          const coverTitle = first ? templateSlideLabel(first) : card.label;
          const preview = templatePreviewColors(card.id, templates);
          return (
            <button
              key={card.id}
              type="button"
              data-testid="slides-template-card"
              data-template-id={card.id}
              disabled={creating}
              onClick={() => onSelect(card.id)}
              className="w-[10.5rem] flex-shrink-0 text-left disabled:cursor-default disabled:opacity-50"
            >
              <div className="relative aspect-video w-full overflow-hidden rounded-sm border border-border bg-background shadow-sm transition-shadow hover:shadow-md">
                {card.blank ? (
                  <div
                    className="absolute inset-0 flex items-center justify-center bg-white"
                    data-testid="slides-template-blank-thumb"
                  >
                    <Plus size={28} className="text-workspace-accent" strokeWidth={2.25} />
                  </div>
                ) : (
                  <SlidesCoverFallback title={coverTitle} preview={preview} />
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

export function SlidesIndexGallery({
  projects,
  workspaceId,
  templates,
  onOpen,
  onRename,
  onArchive,
}: {
  projects: SlidesProject[];
  workspaceId: string;
  templates: SlidesSeedTemplate[];
  onOpen: (project: SlidesProject) => void;
  onRename?: (project: SlidesProject, title: string) => void;
  onArchive?: (project: SlidesProject) => void;
}) {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
      data-testid="slides-index-gallery"
    >
      {projects.map((project) => (
        <SlidesIndexCard
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
