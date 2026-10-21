'use client';

import React, { useState } from 'react';
import { MessageSquare, Pin, MoreVertical, Archive, Edit2, Trash2 } from 'lucide-react';
import './chat-components.css';

export type ConversationItemProps = {
  id: string;
  title: string;
  pinned?: boolean;
  isActive: boolean;
  // Callbacks take the row's id so parents can pass stable functions and the
  // memoized row skips re-rendering when the list re-renders.
  onClick: (id: string) => void;
  onPin: (id: string) => void;
  onArchive: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string, title: string) => void;
  isRenaming?: boolean;
  onStartRename: (id: string) => void;
  onCancelRename: () => void;
  mobilePanel?: boolean;
};

export const ConversationItem = React.memo(function ConversationItem({
  id,
  title,
  pinned,
  isActive,
  onClick,
  onPin,
  onArchive,
  onRename,
  onDelete,
  isRenaming,
  onStartRename,
  onCancelRename,
  mobilePanel = false,
}: ConversationItemProps) {
  const iconSize = mobilePanel ? 14 : 12;
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(title);

  const handleRenameSubmit = () => {
    if (editValue.trim() && editValue !== title) {
      onRename(id, editValue.trim());
    }
    onCancelRename();
  };

  if (isRenaming) {
    return (
      <div className="chat-rename-row">
        <MessageSquare size={iconSize} className="chat-list-row-icon" />
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleRenameSubmit();
            } else if (e.key === 'Escape') {
              onCancelRename();
            }
          }}
          onBlur={handleRenameSubmit}
          autoFocus
          className="chat-rename-input"
        />
      </div>
    );
  }

  return (
    <div className="chat-list-row-wrap">
      <button
        type="button"
        onClick={() => onClick(id)}
        className={`chat-list-row${isActive ? ' is-active' : ''}${mobilePanel ? ' is-mobile-panel' : ''}`}
      >
        {pinned && <Pin size={iconSize} className="chat-list-row-pin" />}
        <MessageSquare size={iconSize} className="chat-list-row-icon" />
        <span className="chat-list-row-title">{title}</span>
        <div
          className="chat-list-row-menu-trigger"
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          }}
          role="presentation"
        >
          <MoreVertical size={12} />
        </div>
      </button>

      {showMenu && (
        <>
          <div className="chat-context-menu-backdrop" onClick={() => setShowMenu(false)} />
          <div className="chat-context-menu">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onPin(id);
                setShowMenu(false);
              }}
              className="chat-context-menu-item"
            >
              <Pin size={12} />
              {pinned ? 'Unpin' : 'Pin'}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onStartRename(id);
                setShowMenu(false);
              }}
              className="chat-context-menu-item"
            >
              <Edit2 size={12} />
              Rename
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onArchive(id);
                setShowMenu(false);
              }}
              className="chat-context-menu-item"
            >
              <Archive size={12} />
              Archive
            </button>
            <div className="chat-context-menu-divider" />
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(id, title);
                setShowMenu(false);
              }}
              className="chat-context-menu-item is-destructive"
            >
              <Trash2 size={12} />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
});
