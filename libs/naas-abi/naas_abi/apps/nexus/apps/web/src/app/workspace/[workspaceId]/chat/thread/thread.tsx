import { ChatInterface } from '@/components/chat/chat-interface';
import { ChatExportButton } from '@/components/chat/chat-export-button';
import { Header } from '@/components/shell/header';

import { ChatMenuBar } from '../components/chat-menu-bar';
import { NEW_CHAT_SLUG } from '../lib/chat-route';

interface ChatThreadPageProps {
  params: Promise<{
    workspaceId: string;
    slug?: string[];
  }>;
}

export default async function ChatThreadPage({ params }: ChatThreadPageProps) {
  const slug = (await params).slug?.[0] ?? null;
  const conversationId = slug === NEW_CHAT_SLUG ? null : slug;
  return (
    <div className="flex h-full flex-col">
      <Header title="Chat" nav={<ChatMenuBar />} actions={<ChatExportButton />} />
      <ChatInterface initialConversationId={conversationId} />
    </div>
  );
}
