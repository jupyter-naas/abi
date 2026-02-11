import { ChatInterface } from '@/components/chat/chat-interface';

interface ChatWorkspacePageProps {
  params: {
    workspaceId: string;
    slug?: string[];
  };
}

export default function ChatWorkspacePage(_: ChatWorkspacePageProps) {
  return <ChatInterface />;
}
