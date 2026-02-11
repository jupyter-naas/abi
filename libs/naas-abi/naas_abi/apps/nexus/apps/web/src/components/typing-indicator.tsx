/**
 * Typing indicator component
 * Shows who's currently typing in a conversation
 */

'use client';

import { useWebSocket } from '@/contexts/websocket-context';
import { useEffect, useState } from 'react';

interface TypingIndicatorProps {
  conversationId: string;
  users?: Array<{ id: string; name: string }>;
}

export function TypingIndicator({ conversationId, users = [] }: TypingIndicatorProps) {
  const { typingUsers } = useWebSocket();
  const [typingUserIds, setTypingUserIds] = useState<string[]>([]);

  useEffect(() => {
    const ids = typingUsers.get(conversationId) || [];
    setTypingUserIds(ids);
  }, [conversationId, typingUsers]);

  if (typingUserIds.length === 0) {
    return null;
  }

  const typingNames = typingUserIds
    .map(id => users.find(u => u.id === id)?.name || 'Someone')
    .slice(0, 3);

  const text = typingNames.length === 1
    ? `${typingNames[0]} is typing...`
    : typingNames.length === 2
    ? `${typingNames[0]} and ${typingNames[1]} are typing...`
    : `${typingNames.slice(0, -1).join(', ')}, and ${typingNames[typingNames.length - 1]} are typing...`;

  return (
    <div className="flex items-center gap-2 px-4 py-2 text-xs text-muted-foreground animate-pulse">
      <div className="flex gap-1">
        <span className="inline-block w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.3s]" />
        <span className="inline-block w-1.5 h-1.5 bg-current rounded-full animate-bounce [animation-delay:-0.15s]" />
        <span className="inline-block w-1.5 h-1.5 bg-current rounded-full animate-bounce" />
      </div>
      <span>{text}</span>
    </div>
  );
}
