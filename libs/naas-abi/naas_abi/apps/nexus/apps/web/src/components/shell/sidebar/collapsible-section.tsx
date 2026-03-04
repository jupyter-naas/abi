'use client';

import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { ChevronRight, Plus } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore, type SidebarSection } from '@/stores/workspace';

export interface SectionProps {
  id: SidebarSection;
  icon: React.ReactNode;
  label: string;
  description?: string;
  href: string;
  collapsed: boolean;
  suppressActiveHighlight?: boolean;
  children?: React.ReactNode;
  onAdd?: () => void;
  onNavigate?: () => void;
}

export function CollapsibleSection({
  id,
  icon,
  label,
  description,
  href,
  collapsed,
  suppressActiveHighlight = false,
  children,
  onAdd,
  onNavigate,
}: SectionProps) {
  const pathname = usePathname();
  const { expandedSections, toggleSection, sidebarCollapsed, toggleSidebar } = useWorkspaceStore();
  const isExpanded = expandedSections.includes(id);
  const isActive = pathname.startsWith(href);
  const hasChildren = Boolean(children);
  const showSectionActive = isActive && !suppressActiveHighlight;
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const sectionRef = useRef<HTMLDivElement>(null);

  const handleIconClick = (e: React.MouseEvent) => {
    if (collapsed && sidebarCollapsed) {
      e.preventDefault();
      toggleSidebar();
    }
  };

  const handleMouseEnter = () => {
    if (description && sectionRef.current) {
      const rect = sectionRef.current.getBoundingClientRect();
      setTooltipPosition({
        top: rect.top,
        left: rect.right + 8,
      });
      setShowTooltip(true);
    }
  };

  return (
    <div className="space-y-0.5">
      <div
        ref={sectionRef}
        className={cn(
          'group/section relative flex items-center gap-1 rounded-lg transition-all',
          showSectionActive && 'text-workspace-accent',
          collapsed && 'justify-center'
        )}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {showTooltip && description && typeof document !== 'undefined' && createPortal(
          <div
            className="fixed z-[100] whitespace-nowrap rounded-md bg-popover px-3 py-2 text-sm shadow-lg border border-border animate-in fade-in-0 zoom-in-95 duration-100"
            style={{ top: tooltipPosition.top, left: tooltipPosition.left }}
          >
            <p className="font-medium">{label}</p>
            <p className="text-muted-foreground text-xs">{description}</p>
          </div>,
          document.body
        )}

        {!collapsed && hasChildren && (
          <button
            onClick={() => toggleSection(id)}
            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground"
          >
            <ChevronRight
              size={14}
              className={cn('transition-transform', isExpanded && 'rotate-90')}
            />
          </button>
        )}

        <Link
          href={href}
          onClick={(e) => {
            handleIconClick(e);
            onNavigate?.();
          }}
          className={cn(
            'flex flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium transition-all',
            'hover:bg-workspace-accent-10 hover:text-workspace-accent',
            showSectionActive && 'bg-workspace-accent-10 text-workspace-accent',
            collapsed && 'px-2 py-2.5 justify-center',
            !collapsed && !hasChildren && 'ml-6'
          )}
        >
          <span className="flex-shrink-0">{icon}</span>
          {!collapsed && <span className="flex-1">{label}</span>}
        </Link>

        {!collapsed && onAdd && (
          <button
            onClick={onAdd}
            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground opacity-0 transition-opacity hover:bg-workspace-accent-10 hover:text-workspace-accent group-hover:opacity-100"
          >
            <Plus size={14} />
          </button>
        )}
      </div>

      {!collapsed && isExpanded && children && (
        <div className="ml-4 space-y-0.5 border-l border-border/50 pl-2">
          {children}
        </div>
      )}
    </div>
  );
}
