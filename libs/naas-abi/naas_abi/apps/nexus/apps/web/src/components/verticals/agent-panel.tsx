'use client';

import { useState } from 'react';
import { Bot, Loader2, Send } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { cn } from '@/lib/utils';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface CompletionResponse {
  choices?: { message?: { content?: string } }[];
}

// Reusable agent chat panel that talks to the OpenAI-compatible shim
// (/api/v1/chat/completions) — the same surface the Continue extension uses.
// `agent` is the abi agent id (the OpenAI "model"). Composable by any vertical.
export function AgentPanel({ agent }: { agent: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const next: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setBusy(true);
    try {
      const res = await authFetch('/api/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: agent,
          messages: next.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      const data = (await res.json()) as CompletionResponse;
      const content = data.choices?.[0]?.message?.content ?? '(no response)';
      setMessages([...next, { role: 'assistant', content }]);
    } catch (e) {
      setMessages([...next, { role: 'assistant', content: `Error: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border/50 px-3 py-2">
        <Bot size={16} className="text-workspace-accent" />
        <span className="text-xs font-medium">Agent · {agent}</span>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 ? (
          <p className="text-xs text-muted-foreground">Ask the agent to get started.</p>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                m.role === 'user'
                  ? 'ml-auto bg-workspace-accent text-white'
                  : 'bg-muted text-foreground',
              )}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
            </div>
          ))
        )}
      </div>
      <div className="flex items-center gap-2 border-t border-border/50 p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void send();
          }}
          placeholder="Message the agent"
          className="flex-1 rounded-md border border-border bg-transparent px-2.5 py-1.5 text-sm outline-none focus:border-workspace-accent"
        />
        <button
          onClick={send}
          disabled={busy || !input.trim()}
          className="flex items-center gap-1.5 rounded-md bg-workspace-accent px-2.5 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          Send
        </button>
      </div>
    </div>
  );
}
