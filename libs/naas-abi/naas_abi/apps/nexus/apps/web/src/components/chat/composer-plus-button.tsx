'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight, Paperclip, Plus, SlidersHorizontal, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useFeature } from '@/hooks/use-feature';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  composerPlusMenuRows,
  type ComposerPlusSkillInput,
} from './composer-plus-menu';
import './composer-plus-menu.css';

export function ComposerPlusButton({
  active = false,
  workspaceId,
  skills,
  onAddFiles,
  onInsertSkill,
}: {
  active?: boolean;
  workspaceId: string | null;
  skills: ComposerPlusSkillInput[] | null;
  onAddFiles: () => void;
  onInsertSkill: (slug: string) => void;
}) {
  const router = useRouter();
  const skillsEnabled = useFeature('skills');
  const [open, setOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const rows = composerPlusMenuRows({ skills, workspaceId, skillsEnabled });

  const close = () => {
    setOpen(false);
    setSkillsOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        close();
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="composer-plus-anchor shrink-0">
      <button
        type="button"
        className={cn('chat-composer-action', (active || open) && 'is-active')}
        title={skillsEnabled ? 'Add files or a skill' : 'Add files'}
        aria-label={skillsEnabled ? 'Add files or a skill' : 'Add files'}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setSkillsOpen(false);
          setOpen((value) => !value);
        }}
      >
        <Plus size={20} />
      </button>

      {open && (
        <div className="composer-plus-menu" role="menu" aria-label="Composer actions">
          {rows.map((row) => {
            if (row.kind === 'files') {
              return (
                <button
                  key={row.id}
                  type="button"
                  role="menuitem"
                  className="composer-plus-menu-item"
                  title="Attach image or document"
                  onClick={() => {
                    close();
                    onAddFiles();
                  }}
                >
                  <Paperclip size={14} />
                  <span className="composer-plus-menu-item-label">{row.label}</span>
                </button>
              );
            }

            if (row.kind === 'skills-loading') {
              return (
                <button
                  key={row.id}
                  type="button"
                  role="menuitem"
                  className="composer-plus-menu-item"
                  disabled
                >
                  <Zap size={14} />
                  <span className="composer-plus-menu-item-body">
                    <span className="composer-plus-menu-item-label">{row.label}</span>
                    <span className="composer-plus-menu-item-meta">{row.hint}</span>
                  </span>
                </button>
              );
            }

            return (
              <div key={row.id} className="composer-plus-submenu-wrap">
                <button
                  type="button"
                  role="menuitem"
                  className={cn('composer-plus-menu-item', skillsOpen && 'is-open')}
                  aria-haspopup="menu"
                  aria-expanded={skillsOpen}
                  onClick={() => setSkillsOpen((value) => !value)}
                >
                  <Zap size={14} />
                  <span className="composer-plus-menu-item-label">{row.label}</span>
                  <ChevronRight
                    size={14}
                    className={cn('composer-plus-chevron', skillsOpen && 'is-open')}
                  />
                </button>
                {skillsOpen && (
                  <div className="composer-plus-submenu" role="menu" aria-label="Skills">
                    {row.skills.map((skill) => (
                      <button
                        key={skill.slug}
                        type="button"
                        role="menuitem"
                        className="composer-plus-menu-item"
                        title={skill.description || skill.name}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          close();
                          onInsertSkill(skill.slug);
                        }}
                      >
                        <span className="composer-plus-menu-item-label">
                          {skill.name}
                          <span className="composer-plus-skill-slug">/{skill.slug}</span>
                        </span>
                      </button>
                    ))}
                    {row.manage && (
                      <>
                        {row.skills.length > 0 && (
                          <div className="composer-plus-submenu-rule" role="separator" />
                        )}
                        <button
                          type="button"
                          role="menuitem"
                          className="composer-plus-menu-item"
                          onClick={() => {
                            const href = row.manage?.href;
                            if (!href) return;
                            close();
                            useWorkspaceStore.getState().setActivePanelSection('settings');
                            router.push(href);
                          }}
                        >
                          <SlidersHorizontal size={14} />
                          <span className="composer-plus-menu-item-label">{row.manage.label}</span>
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
