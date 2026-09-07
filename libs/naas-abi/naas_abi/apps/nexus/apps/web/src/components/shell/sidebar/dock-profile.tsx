'use client';

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { AccountMenuPanel, UserAvatar } from '../account-menu';

const MENU_GAP_PX = 8;
const MENU_WIDTH_PX = 256;

export function DockProfile({ labeled }: { labeled: boolean }) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ left: number; bottom: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const user = useAuthStore((s) => s.user);
  const displayUser = mounted ? user : null;
  const name = displayUser?.name || 'User';

  useEffect(() => {
    setMounted(true);
  }, []);

  const placeMenu = () => {
    const btn = btnRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    setPos({
      left: Math.min(rect.right + MENU_GAP_PX, window.innerWidth - MENU_WIDTH_PX - MENU_GAP_PX),
      bottom: Math.max(MENU_GAP_PX, window.innerHeight - rect.bottom),
    });
  };

  const toggle = () => {
    if (open) {
      setOpen(false);
      return;
    }
    placeMenu();
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (btnRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onReposition = () => placeMenu();

    window.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('resize', onReposition);

    const btn = btnRef.current;
    const observer = btn ? new ResizeObserver(onReposition) : null;
    if (btn && observer) observer.observe(btn);

    return () => {
      window.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('resize', onReposition);
      observer?.disconnect();
    };
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={toggle}
        aria-label={name === 'User' ? 'Account menu' : `${name}, account menu`}
        aria-haspopup="menu"
        aria-expanded={open}
        title={!labeled ? name : undefined}
        className={cn(
          'flex items-center rounded-lg outline-none focus-visible:ring-0',
          'hover:bg-workspace-accent-10',
          open ? 'bg-workspace-accent-10' : '',
          labeled ? 'w-full gap-3 px-3 py-2' : 'h-10 w-10 justify-center',
        )}
      >
        <UserAvatar user={displayUser} className="h-8 w-8 flex-shrink-0" alt="" />
        {labeled && (
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{name}</span>
        )}
      </button>
      {open && mounted && pos && createPortal(
        <div ref={menuRef}>
          <AccountMenuPanel
            user={displayUser}
            onClose={() => setOpen(false)}
            className="fixed"
            style={{ left: pos.left, bottom: pos.bottom }}
          />
        </div>,
        document.body,
      )}
    </>
  );
}
