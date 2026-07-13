import { ChatInterface } from '@/components/chat/chat-interface';
import { Header } from '@/components/shell/header';
import { DriveFileRedirect } from './drive-file-redirect';

interface ChatWorkspacePageProps {
  params: {
    workspaceId: string;
    slug?: string[];
  };
}

export default function ChatWorkspacePage({ params }: ChatWorkspacePageProps) {
  const slug = params.slug ?? [];

  // Drive object paths (naas_abi/<drive>/…) are sometimes emitted as relative
  // file links and get resolved against the current /chat/ URL, landing here.
  // They are not conversation ids — treating slug[0] as one collapsed the URL
  // to /chat/naas_abi. Redirect to the Files page and open the file instead.
  if (slug[0] === 'naas_abi') {
    return <DriveFileRedirect workspaceId={params.workspaceId} objectPath={slug.join('/')} />;
  }

  const conversationId = slug[0] ?? null;
  return (
    <div className="flex h-full flex-col">
      <Header title="Chat" />
      <ChatInterface initialConversationId={conversationId} />
    </div>
  );
}
