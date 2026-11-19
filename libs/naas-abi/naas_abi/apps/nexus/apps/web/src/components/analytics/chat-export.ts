/**
 * A conversation as text, for the Copy button of the message view. Mirrors the backend
 * ``export_conversation_as_response`` txt branch (``chat__primary_adapter__export.py``),
 * so the output matches the chat interface's Export. Only reached by a caller who may
 * read the messages (`ReadAnalyticsConversation`).
 */
import type { ChatDetail } from './types';

export const FEEDBACK_TYPE_LABELS: Record<string, string> = {
  inaccurate: 'Inaccurate response',
  off_topic: 'Off topic',
  hallucination: 'Hallucination / made-up information',
  incomplete: 'Incomplete response',
  unjustified_refusal: 'Unjustified refusal',
  tone: 'Inappropriate style or tone',
  harmful: 'Harmful or problematic content',
  other: 'Other',
};

export function buildChatExportText(conversation: ChatDetail, exportedAt: string = new Date().toISOString()): string {
  const SEP_TOP = '='.repeat(80);
  const SEP_BTW = '-'.repeat(80);
  const title = conversation.title || 'Untitled Conversation';

  let out = `Conversation: ${title}\n`;
  out += `ID: ${conversation.conversation_id}\n`;
  out += `Exported: ${exportedAt}\n`;
  out += `User: ${conversation.user_id}\n`;
  out += `Workspace: ${conversation.workspace_id}\n`;
  out += `Messages: ${conversation.messages.length}\n`;
  out += `\n${SEP_TOP}\n\n`;

  for (const msg of conversation.messages) {
    let role = msg.role.toUpperCase();
    if (msg.role === 'assistant' && msg.agent) {
      role = `ASSISTANT (${msg.agent})`;
    }
    out += `[${role}]\n`;
    if (msg.created_at) out += `Timestamp: ${msg.created_at}\n`;
    const exec = msg.metadata?.execution_time;
    if (typeof exec === 'number') {
      out += `Execution time: ${exec.toFixed(1)}s\n`;
    }
    const fb = msg.metadata?.feedback;
    if (fb === 'like' || fb === 'dislike') {
      out += `Feedback: ${fb}\n`;
      if (fb === 'dislike') {
        const fbType = msg.metadata?.feedback_type;
        if (typeof fbType === 'string' && fbType) {
          out += `Feedback type: ${fbType}\n`;
        }
        const fbSeverity = msg.metadata?.feedback_severity;
        if (typeof fbSeverity === 'number') {
          out += `Feedback severity: ${fbSeverity}/5\n`;
        }
        const fbDetail = msg.metadata?.feedback_detail;
        if (typeof fbDetail === 'string' && fbDetail) {
          out += `Feedback detail: ${fbDetail}\n`;
        }
      }
    }
    const steps = msg.metadata?.steps ?? [];
    if (steps.length > 0) {
      out += 'Steps:\n';
      for (const s of steps) {
        const prefix = s.prefix || 'Tool';
        const name = s.tool_name || '';
        const status = s.status || '';
        out += `  - [${prefix}] ${name} — ${status}\n`;
        if (s.input) out += `      input: ${s.input}\n`;
        if (s.output) out += `      output: ${s.output}\n`;
      }
      out += '\n';
    }
    if (msg.role === 'assistant') {
      out += 'Message:\n';
    }
    out += `${msg.content}\n`;
    out += `\n${SEP_BTW}\n\n`;
  }

  return out;
}
