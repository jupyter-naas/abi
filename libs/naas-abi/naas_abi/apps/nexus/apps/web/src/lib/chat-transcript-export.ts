/**
 * Client-side chat transcript export for the Nexus AI pane (and any chrome
 * that already holds conversation messages in the workspace store).
 *
 * Prefer this over the server /export endpoint for the pane: drafts may not be
 * persisted yet, and the store already has the live user/assistant turns.
 */

export type TranscriptFormat = 'md' | 'txt';

export interface TranscriptMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
  timestamp?: Date | string;
}

export interface TranscriptConversation {
  id: string;
  title: string;
  messages: TranscriptMessage[];
  workspaceId?: string;
}

function iso(value: Date | string | undefined): string {
  if (!value) return '';
  if (value instanceof Date) return value.toISOString();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toISOString();
}

function visibleMessages(messages: TranscriptMessage[]): TranscriptMessage[] {
  return messages.filter((m) => m.role === 'user' || m.role === 'assistant');
}

function roleHeading(msg: TranscriptMessage, format: TranscriptFormat): string {
  if (msg.role === 'user') return format === 'md' ? '## User' : '[USER]';
  const agent = msg.agent?.trim();
  if (format === 'md') {
    return agent ? `## Assistant (${agent})` : '## Assistant';
  }
  return agent ? `[ASSISTANT (${agent})]` : '[ASSISTANT]';
}

/** Markdown transcript of user/assistant turns. */
export function formatTranscriptMarkdown(conversation: TranscriptConversation): string {
  const title = conversation.title?.trim() || 'Untitled conversation';
  const messages = visibleMessages(conversation.messages);
  const exportedAt = new Date().toISOString();

  let out = `# ${title}\n\n`;
  out += `**Conversation ID:** \`${conversation.id}\`  \n`;
  out += `**Exported:** ${exportedAt}  \n`;
  if (conversation.workspaceId) {
    out += `**Workspace:** \`${conversation.workspaceId}\`  \n`;
  }
  out += `**Messages:** ${messages.length}\n\n`;
  out += '---\n\n';

  for (const msg of messages) {
    out += `${roleHeading(msg, 'md')}\n\n`;
    const when = iso(msg.timestamp);
    if (when) out += `*${when}*\n\n`;
    out += `${msg.content || ''}\n\n`;
    out += '---\n\n';
  }

  return out;
}

/** Plain-text transcript of user/assistant turns. */
export function formatTranscriptText(conversation: TranscriptConversation): string {
  const title = conversation.title?.trim() || 'Untitled conversation';
  const messages = visibleMessages(conversation.messages);
  const exportedAt = new Date().toISOString();

  let out = `Conversation: ${title}\n`;
  out += `ID: ${conversation.id}\n`;
  out += `Exported: ${exportedAt}\n`;
  if (conversation.workspaceId) {
    out += `Workspace: ${conversation.workspaceId}\n`;
  }
  out += `Messages: ${messages.length}\n`;
  out += `\n${'='.repeat(80)}\n\n`;

  for (const msg of messages) {
    out += `${roleHeading(msg, 'txt')}\n`;
    const when = iso(msg.timestamp);
    if (when) out += `Timestamp: ${when}\n`;
    out += `${msg.content || ''}\n`;
    out += `\n${'-'.repeat(80)}\n\n`;
  }

  return out;
}

export function formatTranscript(
  conversation: TranscriptConversation,
  format: TranscriptFormat
): string {
  return format === 'txt'
    ? formatTranscriptText(conversation)
    : formatTranscriptMarkdown(conversation);
}

export function transcriptFilename(
  conversation: TranscriptConversation,
  format: TranscriptFormat
): string {
  const slug = (conversation.title?.trim() || 'conversation')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'conversation';
  return `${slug}-${conversation.id}-${Date.now()}.${format}`;
}

/** Trigger a browser download for a text payload. */
export function downloadTextFile(
  filename: string,
  content: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/** Format + download the current conversation transcript. */
export function downloadConversationTranscript(
  conversation: TranscriptConversation,
  format: TranscriptFormat = 'md'
): void {
  const content = formatTranscript(conversation, format);
  const mime = format === 'txt' ? 'text/plain;charset=utf-8' : 'text/markdown;charset=utf-8';
  downloadTextFile(transcriptFilename(conversation, format), content, mime);
}
