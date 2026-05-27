import { ChatInterface } from '@/components/chat/chat-interface';
import { Header } from '@/components/shell/header';

interface ChatWorkspacePageProps {
  params: {
    workspaceId: string;
    slug?: string[];
  };
}

export default function ChatWorkspacePage({ params }: ChatWorkspacePageProps) {
  const conversationId = params.slug?.[0] ?? null;
  return (
    <div className="flex h-full flex-col">
      <Header title="Chat" />
      <ChatInterface initialConversationId={conversationId} />
    </div>
  );
}
