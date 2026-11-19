import { describe, expect, it } from 'vitest';
import { buildChatExportText } from './chat-export';

describe('buildChatExportText', () => {
  it('writes the conversation header, then each message with its feedback and steps', () => {
    const text = buildChatExportText(
      {
        conversation_id: 'c-1',
        workspace_id: 'ws-1',
        user_id: 'u-1',
        title: 'Hello',
        agent: 'abi',
        messages: [
          { id: 'm1', role: 'user', content: 'Hi' },
          {
            id: 'm2',
            role: 'assistant',
            agent: 'abi',
            content: 'Hello!',
            metadata: {
              feedback: 'dislike',
              feedback_type: 'tone',
              steps: [{ tool_name: 'search', prefix: 'Tool', status: 'done', input: 'q' }],
            },
          },
        ],
      },
      '2026-11-19T00:00:00Z'
    );
    expect(text).toContain('Conversation: Hello\nID: c-1\nExported: 2026-11-19T00:00:00Z\nUser: u-1\nWorkspace: ws-1\nMessages: 2\n');
    expect(text).toContain('[USER]\nHi\n');
    expect(text).toContain('[ASSISTANT (abi)]\nFeedback: dislike\nFeedback type: tone\nSteps:\n  - [Tool] search — done\n      input: q\n');
  });
});
