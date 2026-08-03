import { describe, expect, it } from 'vitest';
import {
  formatTranscriptMarkdown,
  formatTranscriptText,
  transcriptFilename,
  type TranscriptConversation,
} from './chat-transcript-export';

const sample: TranscriptConversation = {
  id: 'conv-abc123',
  title: 'Maps briefing',
  workspaceId: 'ws-1',
  messages: [
    {
      role: 'user',
      content: 'Show wildfires near Paris',
      timestamp: '2026-07-30T10:00:00.000Z',
    },
    {
      role: 'system',
      content: 'internal',
    },
    {
      role: 'assistant',
      content: 'Here are the active fires.',
      agent: 'Abi',
      timestamp: '2026-07-30T10:00:05.000Z',
    },
  ],
};

describe('formatTranscriptMarkdown', () => {
  it('exports user and assistant turns as markdown', () => {
    const md = formatTranscriptMarkdown(sample);
    expect(md).toContain('# Maps briefing');
    expect(md).toContain('**Conversation ID:** `conv-abc123`');
    expect(md).toContain('## User');
    expect(md).toContain('Show wildfires near Paris');
    expect(md).toContain('## Assistant (Abi)');
    expect(md).toContain('Here are the active fires.');
    expect(md).not.toContain('internal');
  });
});

describe('formatTranscriptText', () => {
  it('exports user and assistant turns as plain text', () => {
    const txt = formatTranscriptText(sample);
    expect(txt).toContain('Conversation: Maps briefing');
    expect(txt).toContain('[USER]');
    expect(txt).toContain('Show wildfires near Paris');
    expect(txt).toContain('[ASSISTANT (Abi)]');
    expect(txt).not.toContain('internal');
  });
});

describe('transcriptFilename', () => {
  it('slugifies the title and keeps the conversation id', () => {
    const name = transcriptFilename(sample, 'md');
    expect(name).toMatch(/^maps-briefing-conv-abc123-\d+\.md$/);
  });
});
