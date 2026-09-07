import { ChatInterface } from '@/components/chat/chat-interface';
import { ChatExportButton } from '@/components/chat/chat-export-button';
import { Header } from '@/components/shell/header';

import { NEW_CHAT_SLUG } from '../lib/chat-route';

interface ChatThreadPageProps {
  params: {
    workspaceId: string;
    slug?: string[];
  };
}

export default function ChatThreadPage({ params }: ChatThreadPageProps) {
  const slug = params.slug?.[0] ?? null;
  const conversationId = slug === NEW_CHAT_SLUG ? null : slug;
  return (
    <div className="flex h-full flex-col">
      <Header title="Chat" actions={<ChatExportButton />} />
      <ChatInterface initialConversationId={conversationId} />
    </div>
  );
}
