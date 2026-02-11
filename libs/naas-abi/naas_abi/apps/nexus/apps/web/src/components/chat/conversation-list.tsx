'use client';

import { useState, useEffect } from 'react';
import { Plus, MessageSquare, MoreVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';

export function ConversationList() {
  const [mounted, setMounted] = useState(false);
  const {
    conversations,
    activeConversationId,
    createConversation,
    setActiveConversation,
  } = useWorkspaceStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Use empty state on server to prevent hydration mismatch
  const displayConversations = mounted ? conversations : [];
  const displayActiveId = mounted ? activeConversationId : null;

  return (
    <div className="flex h-full w-64 flex-col border-r border-border/50 bg-card/50">
      {/* Header */}
      <div className="flex h-12 items-center justify-between border-b border-border/50 px-3">
        <span className="text-sm font-medium">Conversations</span>
        <button
          onClick={() => createConversation()}
          className={cn(
            'flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors',
            'hover:bg-primary/10 hover:text-primary'
          )}
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-auto p-2">
        {displayConversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <MessageSquare size={32} className="mb-3 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">No conversations yet</p>
            <button
              onClick={() => createConversation()}
              className="mt-3 text-sm font-medium text-primary hover:underline"
            >
              Start a conversation
            </button>
          </div>
        ) : (
          <div className="space-y-1">
            {displayConversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setActiveConversation(conv.id)}
                className={cn(
                  'group flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  'hover:bg-primary/10',
                  displayActiveId === conv.id && 'bg-primary/15 text-primary'
                )}
              >
                <MessageSquare size={14} className="flex-shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate">{conv.title}</span>
                <button
                  className={cn(
                    'flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-100',
                    'hover:text-foreground'
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    // TODO: Show conversation menu
                  }}
                >
                  <MoreVertical size={14} />
                </button>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
