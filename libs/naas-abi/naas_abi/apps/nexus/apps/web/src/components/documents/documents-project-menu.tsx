'use client';

import { useEffect, useLayoutEffect, useRef, useState, type Ref } from 'react';
import { createPortal } from 'react-dom';
import { Archive, Edit2, MoreVertical } from 'lucide-react';
import '@/app/workspace/[workspaceId]/chat/components/chat-components.css';
import './documents-project-menu.css';

/**
 * Same overflow as a chat conversation row: hover kebab, Rename, Archive.
 * Pin/Delete stay off; documents are git projects, not chat threads.
 *
 * Chat rows keep the panel in-flow (`position: absolute; top: 100%`). Gallery
 * cards clip that: `overflow-hidden` on the glass card plus `overflow-auto`
 * on the sections pane and the status footer. Portal + fixed + flip so last-row
 * (and any clipped) menus stay on screen.
 */
export const SLIDES_PROJECT_MENU_WIDTH_PX = 160;
export const SLIDES_PROJECT_MENU_HEIGHT_PX = 68;
export const SLIDES_PROJECT_MENU_GAP_PX = 4;
/** Platform status footer is `h-7` (28px). Keep the panel clear of it. */
export const SLIDES_PROJECT_MENU_FOOTER_PX = 28;

export type DocumentsProjectMenuPlacement = {
  top: number;
  left: number;
  placement: 'above' | 'below';
};

export function placeDocumentsProjectMenu(
  trigger: { top: number; right: number; bottom: number },
  viewport: { width: number; height: number },
  menu: { width: number; height: number } = {
    width: SLIDES_PROJECT_MENU_WIDTH_PX,
    height: SLIDES_PROJECT_MENU_HEIGHT_PX,
  },
): DocumentsProjectMenuPlacement {
  const gap = SLIDES_PROJECT_MENU_GAP_PX;
  const footer = SLIDES_PROJECT_MENU_FOOTER_PX;
  const usableBottom = viewport.height - footer;
  const spaceBelow = usableBottom - trigger.bottom - gap;
  const spaceAbove = trigger.top - gap;
  const placement =
    spaceBelow >= menu.height || spaceBelow >= spaceAbove ? 'below' : 'above';

  let top =
    placement === 'above'
      ? trigger.top - gap - menu.height
      : trigger.bottom + gap;
  const maxTop = usableBottom - menu.height;
  top = Math.min(Math.max(0, top), Math.max(0, maxTop));

  let left = trigger.right - menu.width;
  left = Math.min(
    Math.max(8, left),
    Math.max(8, viewport.width - menu.width - 8),
  );

  return { top, left, placement };
}

const useIsoLayoutEffect =
  typeof window !== 'undefined' ? useLayoutEffect : useEffect;

function DocumentsProjectMenuPanel({
  onRename,
  onArchive,
  onOpenChange,
  pos,
  menuRef,
}: {
  onRename: () => void;
  onArchive: () => void;
  onOpenChange: (open: boolean) => void;
  pos: DocumentsProjectMenuPlacement | null;
  menuRef?: Ref<HTMLDivElement>;
}) {
  return (
    <>
      <div
        className="chat-context-menu-backdrop documents-project-menu-backdrop"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenChange(false);
        }}
      />
      <div
        ref={menuRef}
        className={`chat-context-menu documents-project-menu-panel${pos ? '' : ' is-measuring'}`}
        data-testid="documents-project-menu-panel"
        data-placement={pos?.placement ?? 'below'}
        style={
          pos
            ? {
                position: 'fixed',
                top: pos.top,
                left: pos.left,
                right: 'auto',
                marginTop: 0,
              }
            : undefined
        }
      >
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onRename();
            onOpenChange(false);
          }}
          className="chat-context-menu-item"
        >
          <Edit2 size={12} />
          Rename
        </button>
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onArchive();
            onOpenChange(false);
          }}
          className="chat-context-menu-item"
        >
          <Archive size={12} />
          Archive
        </button>
      </div>
    </>
  );
}

export function DocumentsProjectOverflowMenu({
  open,
  onOpenChange,
  onRename,
  onArchive,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRename: () => void;
  onArchive: () => void;
}) {
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<DocumentsProjectMenuPlacement | null>(null);
  const canPortal = typeof document !== 'undefined';

  useIsoLayoutEffect(() => {
    if (!open || !canPortal) {
      setPos(null);
      return;
    }
    const update = () => {
      const trigger = triggerRef.current;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const menuEl = menuRef.current;
      setPos(
        placeDocumentsProjectMenu(
          rect,
          { width: window.innerWidth, height: window.innerHeight },
          {
            width: menuEl?.offsetWidth || SLIDES_PROJECT_MENU_WIDTH_PX,
            height: menuEl?.offsetHeight || SLIDES_PROJECT_MENU_HEIGHT_PX,
          },
        ),
      );
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open, canPortal]);

  const panel = open ? (
    <DocumentsProjectMenuPanel
      onRename={onRename}
      onArchive={onArchive}
      onOpenChange={onOpenChange}
      pos={canPortal ? pos : null}
      menuRef={menuRef}
    />
  ) : null;

  return (
    <div className="chat-list-row-wrap" data-testid="documents-project-menu">
      <div
        ref={triggerRef}
        className="chat-list-row-menu-trigger"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onOpenChange(!open);
        }}
        role="document"
      >
        <MoreVertical size={12} />
      </div>
      {open && !canPortal ? panel : null}
      {open && canPortal
        ? createPortal(panel, document.body)
        : null}
    </div>
  );
}
