import { ChatInterface } from '@/components/chat/chat-interface';
import { ChatExportButton } from '@/components/chat/chat-export-button';
import { NEW_CHAT_SLUG } from '@/components/shell/chat-route';
import { Header } from '@/components/shell/header';

interface ChatWorkspacePageProps {
  params: {
    workspaceId: string;
    slug?: string[];
  };
}

export default function ChatWorkspacePage({ params }: ChatWorkspacePageProps) {
  const slug = params.slug?.[0] ?? null;
  const conversationId = slug === NEW_CHAT_SLUG ? null : slug;
  return (
    <div className="flex h-full flex-col">
      <Header title="Chat" actions={<ChatExportButton />} />
      <ChatInterface initialConversationId={conversationId} />
    </div>
  );
}
