'use client';

import React, { useState } from 'react';
import { ChevronRight, Folder } from 'lucide-react';
import { ConversationItem } from './conversation-item';
import './chat-components.css';

export type ProjectGroupProps = {
  name: string;
  conversations: { id: string; title: string; pinned?: boolean }[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onPin: (id: string) => void;
  onArchive: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
  renamingId: string | null;
  onStartRename: (id: string) => void;
  onCancelRename: () => void;
  mobilePanel?: boolean;
};

export const ProjectGroup = React.memo(function ProjectGroup({
  name,
  conversations,
  activeId,
  onSelect,
  onPin,
  onArchive,
  onRename,
  onDelete,
  renamingId,
  onStartRename,
  onCancelRename,
  mobilePanel = false,
}: ProjectGroupProps) {
  const iconSize = mobilePanel ? 14 : 12;
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="chat-project-group">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className={`chat-project-header${mobilePanel ? ' is-mobile-panel' : ''}`}
      >
        <ChevronRight
          size={iconSize}
          className={`chat-project-chevron${expanded ? ' is-expanded' : ''}`}
        />
        <Folder size={iconSize} />
        <span className="chat-list-row-title">{name}</span>
        <span className="chat-project-count">{conversations.length}</span>
      </button>
      {expanded && (
        <div className="chat-project-children">
          {conversations.map((conv) => (
            <ConversationItem
              key={conv.id}
              id={conv.id}
              title={conv.title}
              pinned={conv.pinned}
              isActive={activeId === conv.id}
              onClick={() => onSelect(conv.id)}
              onPin={() => onPin(conv.id)}
              onArchive={() => onArchive(conv.id)}
              isRenaming={renamingId === conv.id}
              onStartRename={() => onStartRename(conv.id)}
              onRename={(newTitle) => onRename(conv.id, newTitle)}
              onCancelRename={onCancelRename}
              onDelete={() => onDelete(conv.id)}
              mobilePanel={mobilePanel}
            />
          ))}
        </div>
      )}
    </div>
  );
});
