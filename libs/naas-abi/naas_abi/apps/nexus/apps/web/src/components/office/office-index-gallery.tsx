'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus } from 'lucide-react';
import { OfficeCoverFallback, OfficeCoverThumb, type OfficeCoverFit } from './office-cover-thumb';
import { officeItemHref, type OfficeKind } from './office-kinds';
import { OfficeProjectMenu } from './office-project-menu';
import { OFFICE_TEMPLATE_CATALOGS } from './office-templates';

/** The fields of a project a gallery card reads. */
export type OfficeGalleryProject = { slug: string; title: string; template_id: string };

/** A seed template as the gallery reads it: its colours and its parts. */
export type OfficeGalleryTemplate = {
  id: string;
  name: string;
  preview_bg: string;
  preview_panel: string;
  preview_accent: string;
  preview_ink: string;
} & Partial<Record<OfficeKind['templateParts'], Array<{ eyebrow: string; title: string }>>>;

export function OfficeIndexCard({
  kind,
  fit,
  project,
  workspaceId,
  templates,
  onOpen,
  onRename,
  onArchive,
}: {
  kind: OfficeKind;
  fit: OfficeCoverFit;
  project: OfficeGalleryProject;
  workspaceId: string;
  templates: OfficeGalleryTemplate[];
  onOpen: () => void;
  onRename?: (title: string) => void;
  onArchive?: () => void;
}) {
  const preview = OFFICE_TEMPLATE_CATALOGS[kind.id].previewColors(project.template_id, templates);
  const href = officeItemHref(kind, workspaceId, project.slug);
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
      data-testid={`${kind.testIdPrefix}-index-card`}
      data-slug={project.slug}
      className="group/office-card glass-card relative flex flex-col overflow-hidden transition-all hover:-translate-y-0.5 hover:border-workspace-accent/40 hover:shadow-md"
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
        <OfficeCoverThumb
          kind={kind}
          fit={fit}
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
            data-testid={`${kind.testIdPrefix}-rename-input`}
          />
        ) : (
          <Link href={href} onClick={onOpen} className="min-w-0 flex-1 no-underline">
            <h3 className="truncate font-semibold leading-tight text-foreground">{project.title}</h3>
          </Link>
        )}
        {onRename && onArchive && !renaming ? (
          <OfficeProjectMenu
            kind={kind}
            open={showMenu}
            onOpenChange={setShowMenu}
            triggerClassName="opacity-0 focus-visible:opacity-100 group-hover/office-card:opacity-100 data-[state=open]:opacity-100 max-md:opacity-100"
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

export function OfficeTemplateStrip({
  kind,
  templates,
  creating,
  onSelect,
}: {
  kind: OfficeKind;
  templates: OfficeGalleryTemplate[];
  creating?: boolean;
  onSelect: (templateId: string) => void;
}) {
  const catalog = OFFICE_TEMPLATE_CATALOGS[kind.id];
  const cards = catalog.homeCards(templates);
  const prefix = kind.testIdPrefix;

  return (
    <section data-testid={`${prefix}-template-strip`} className="border-b border-border bg-muted/50 px-6 py-5">
      <h2 className="mb-4 text-sm font-medium text-foreground">{kind.startLabel}</h2>
      <div className="flex gap-4 overflow-x-auto pb-1">
        {cards.map((card) => {
          const seed = templates.find((row) => row.id === card.id);
          const first = seed?.[kind.templateParts]?.[0];
          const coverTitle = first ? catalog.partLabel(first) : card.label;
          const preview = catalog.previewColors(card.id, templates);
          return (
            <button
              key={card.id}
              type="button"
              data-testid={`${prefix}-template-card`}
              data-template-id={card.id}
              disabled={creating}
              onClick={() => onSelect(card.id)}
              className="w-[10.5rem] flex-shrink-0 text-left disabled:cursor-default disabled:opacity-50"
            >
              <div
                className={`relative ${kind.aspectClass} w-full overflow-hidden rounded-sm border border-border bg-background shadow-sm transition-shadow hover:shadow-md`}
              >
                {card.blank ? (
                  <div
                    className="absolute inset-0 flex items-center justify-center bg-white"
                    data-testid={`${prefix}-template-blank-thumb`}
                  >
                    <Plus size={28} className="text-workspace-accent" strokeWidth={2.25} />
                  </div>
                ) : (
                  <OfficeCoverFallback kind={kind} title={coverTitle} preview={preview} />
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

export function OfficeIndexGallery<P extends OfficeGalleryProject>({
  kind,
  fit,
  projects,
  workspaceId,
  templates,
  onOpen,
  onRename,
  onArchive,
}: {
  kind: OfficeKind;
  fit: OfficeCoverFit;
  projects: P[];
  workspaceId: string;
  templates: OfficeGalleryTemplate[];
  onOpen: (project: P) => void;
  onRename?: (project: P, title: string) => void;
  onArchive?: (project: P) => void;
}) {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
      data-testid={`${kind.id}-index-gallery`}
    >
      {projects.map((project) => (
        <OfficeIndexCard
          key={project.slug}
          kind={kind}
          fit={fit}
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
