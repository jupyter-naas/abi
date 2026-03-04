/**
 * WebSocket context for real-time features
 * 
 * Provides:
 * - Socket.IO connection management
 * - Presence tracking
 * - Typing indicators
 * - Live updates
 */

'use client';

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/stores/auth';
import { getApiUrl, getWebsocketPath } from '@/lib/config';

interface PresenceUser {
  user_id: string;
  timestamp: string;
}

interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  presenceUsers: string[];
  typingUsers: Map<string, string[]>; // conversation_id -> user_ids[]
  joinWorkspace: (workspaceId: string) => void;
  leaveWorkspace: (workspaceId: string) => void;
  startTyping: (workspaceId: string, conversationId: string) => void;
  stopTyping: (workspaceId: string, conversationId: string) => void;
  onMessage: (callback: (data: any) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [presenceUsers, setPresenceUsers] = useState<string[]>([]);
  const [typingUsers, setTypingUsers] = useState<Map<string, string[]>>(new Map());

  // Initialize socket connection
  useEffect(() => {
    if (!user || !token) {
      setSocket(null);
      setIsConnected(false);
      return;
    }

    const apiUrl = getApiUrl();
    const websocketPath = getWebsocketPath();

    const socketInstance = io(apiUrl, {
      path: websocketPath,
      auth: { authorization: `Bearer ${token}` },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    socketInstance.on('connect', () => {
      console.log('✓ WebSocket connected');
      setIsConnected(true);
    });

    socketInstance.on('disconnect', () => {
      console.log('✗ WebSocket disconnected');
      setIsConnected(false);
    });

    socketInstance.on('connect_error', (error: Error & { data?: { status?: number } }) => {
      const message = error.message.toLowerCase();
      const status = error.data?.status;
      const isAuthError =
        status === 401 ||
        status === 403 ||
        message.includes('401') ||
        message.includes('403') ||
        message.includes('unauthorized') ||
        message.includes('forbidden');

      // Stop retry loop on auth failures; reconnect will happen when token changes.
      if (isAuthError) {
        socketInstance.io.opts.reconnection = false;
        socketInstance.disconnect();
        useAuthStore.getState().logout();
        if (typeof window !== 'undefined') {
          window.location.href = '/login';
        }
        return;
      }
      console.error('WebSocket connection error:', error);
    });

    // Presence events
    socketInstance.on('user_joined', (data: PresenceUser) => {
      setPresenceUsers(prev => {
        if (!prev.includes(data.user_id)) {
          return [...prev, data.user_id];
        }
        return prev;
      });
    });

    socketInstance.on('user_left', (data: { user_id: string }) => {
      setPresenceUsers(prev => prev.filter(id => id !== data.user_id));
    });

    // Typing events
    socketInstance.on('user_typing', (data: { 
      user_id: string; 
      conversation_id: string; 
      typing: boolean 
    }) => {
      setTypingUsers(prev => {
        const newMap = new Map(prev);
        const conversationTypers = newMap.get(data.conversation_id) || [];
        
        if (data.typing) {
          if (!conversationTypers.includes(data.user_id)) {
            newMap.set(data.conversation_id, [...conversationTypers, data.user_id]);
          }
        } else {
          newMap.set(
            data.conversation_id, 
            conversationTypers.filter(id => id !== data.user_id)
          );
        }
        
        return newMap;
      });
    });

    setSocket(socketInstance);

    return () => {
      socketInstance.disconnect();
    };
  }, [user, token]);

  const joinWorkspace = useCallback((workspaceId: string) => {
    if (!socket) return;
    
    socket.emit('join_workspace', { workspace_id: workspaceId }, (response: any) => {
      if (response.users) {
        setPresenceUsers(response.users);
      }
    });
  }, [socket]);

  const leaveWorkspace = useCallback((workspaceId: string) => {
    if (!socket) return;
    
    socket.emit('leave_workspace', { workspace_id: workspaceId });
    setPresenceUsers([]);
  }, [socket]);

  const startTyping = useCallback((workspaceId: string, conversationId: string) => {
    if (!socket) return;
    
    socket.emit('typing_start', {
      workspace_id: workspaceId,
      conversation_id: conversationId
    });
  }, [socket]);

  const stopTyping = useCallback((workspaceId: string, conversationId: string) => {
    if (!socket) return;
    
    socket.emit('typing_stop', {
      workspace_id: workspaceId,
      conversation_id: conversationId
    });
  }, [socket]);

  const onMessage = useCallback((callback: (data: any) => void) => {
    if (!socket) return () => {};
    
    socket.on('new_message', callback);
    
    return () => {
      socket.off('new_message', callback);
    };
  }, [socket]);

  const value: WebSocketContextType = {
    socket,
    isConnected,
    presenceUsers,
    typingUsers,
    joinWorkspace,
    leaveWorkspace,
    startTyping,
    stopTyping,
    onMessage
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
}
