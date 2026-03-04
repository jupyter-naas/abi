/**
 * Presence indicator component
 * Shows who's currently online in the workspace
 */

'use client';

import { useEffect } from 'react';
import { useWebSocket } from '@/contexts/websocket-context';
import { Circle } from 'lucide-react';

interface PresenceIndicatorProps {
  workspaceId: string;
  users?: Array<{ id: string; name: string; email: string }>;
}

export function PresenceIndicator({ workspaceId, users = [] }: PresenceIndicatorProps) {
  const { presenceUsers, joinWorkspace, leaveWorkspace, isConnected } = useWebSocket();

  useEffect(() => {
    joinWorkspace(workspaceId);
    
    return () => {
      leaveWorkspace(workspaceId);
    };
  }, [workspaceId, joinWorkspace, leaveWorkspace]);

  const onlineUsers = users.filter(user => presenceUsers.includes(user.id));

  if (!isConnected || onlineUsers.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 px-4 py-2 border-b border-border/40">
      <Circle className="h-2 w-2 fill-green-500 text-green-500" />
      <span className="text-xs text-muted-foreground">
        {onlineUsers.length} {onlineUsers.length === 1 ? 'person' : 'people'} online
      </span>
      
      <div className="flex -space-x-2 ml-2">
        {onlineUsers.slice(0, 5).map((user) => (
          <div
            key={user.id}
            className="flex items-center justify-center h-6 w-6 rounded-full bg-primary/10 text-xs font-medium border-2 border-background"
            title={user.name}
          >
            {user.name.split(' ').map(n => n[0]).join('').toUpperCase()}
          </div>
        ))}
        {onlineUsers.length > 5 && (
          <div className="flex items-center justify-center h-6 w-6 rounded-full bg-muted border-2 border-background">
            <span className="text-[10px] text-muted-foreground">
              +{onlineUsers.length - 5}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
