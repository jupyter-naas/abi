'use client';

import { useCallback, useMemo, useState } from 'react';
import { Activity, Globe, Lock, MessageSquare, ThumbsDown, ThumbsUp, TrendingUp, Users } from 'lucide-react';
import { BarList, type BarItem } from '../bar-list';
import { Card } from '../card';
import { ConversationsTable } from '../conversations-table';
import { formatDateTime, formatNumber } from '../format';
import { KpiCard } from '../kpi-card';
import { LineChart } from '../line-chart';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import { perBucket } from './overview-tab';
import { ChatDetailView } from './chat-detail';
import type { AnalyticsTabProps } from '../tabs';
import type { ChatAnalyticsResponse, UsersDirectoryEntry } from '../types';

/**
 * Chat figures and the conversations of the period. Without `ReadAnalyticsConversation`
 * (`canReadMessages` false) the list is metadata only: no message view, no copy/export.
 */
export function ChatsTab({
  scope,
  filters,
  timeZone,
  granularity,
  onUserPick,
  canReadMessages,
  directory,
}: AnalyticsTabProps & { canReadMessages: boolean; directory: UsersDirectoryEntry[] }) {
  const { data, loading, error } = useAnalytics<ChatAnalyticsResponse>(scope, '/chat-analytics', filters);
  const [openId, setOpenId] = useState<string | null>(null);
  const [barFilter, setBarFilter] = useState<{ col: 'agents' | 'tools'; value: string } | null>(null);

  // The table knows emails only: a row's user is picked through the scope's directory.
  const userIdByEmail = useMemo(() => new Map(directory.map((u) => [u.user_email, u.user_id])), [directory]);
  const pickByEmail = useCallback(
    (email: string) => {
      const userId = userIdByEmail.get(email);
      if (userId) onUserPick(userId);
    },
    [userIdByEmail, onUserPick]
  );
  const canPickUser = useCallback((email: string) => userIdByEmail.has(email), [userIdByEmail]);
  const formatInZone = useCallback((iso: string) => formatDateTime(iso, timeZone), [timeZone]);

  function handleBarClick(col: 'agents' | 'tools', value: string) {
    setBarFilter((prev) => (prev?.col === col && prev.value === value ? null : { col, value }));
  }

  if (openId && canReadMessages) {
    return <ChatDetailView scope={scope} conversationId={openId} timeZone={timeZone} onClose={() => setOpenId(null)} />;
  }

  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;

  const k = data.kpi;
  const isEmpty = k.num_chats === 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="Chats" value={formatNumber(k.num_chats)} icon={MessageSquare} />
        <KpiCard label="Messages" value={formatNumber(k.num_messages)} icon={Activity} />
        <KpiCard label="Likes" value={formatNumber(k.messages_liked)} icon={ThumbsUp} />
        <KpiCard label="Dislikes" value={formatNumber(k.messages_disliked)} icon={ThumbsDown} />
        <KpiCard label="Agents used" value={k.agents_used} icon={Users} />
        <KpiCard label="Most used agent" value={k.most_agent_used ?? '—'} icon={TrendingUp} />
        <KpiCard label="Tools used" value={k.tools_used} icon={Globe} />
        <KpiCard label="Most used tool" value={k.most_tool_used ?? '—'} icon={TrendingUp} />
      </div>

      {isEmpty ? (
        <Card title="No chat activity in this period">
          <EmptyBlock>Try another period or remove the filters.</EmptyBlock>
        </Card>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Chats over time" subtitle={`Conversations ${perBucket(granularity)}`}>
              <LineChart data={data.chats_over_time} granularity={granularity} label="chats" />
            </Card>
            <Card title="Messages over time" subtitle={`Messages sent ${perBucket(granularity)}`}>
              <LineChart data={data.messages_over_time} granularity={granularity} label="messages" />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Agent usage" subtitle="Messages per agent — click to filter the conversations">
              <div className="max-h-[200px] overflow-y-auto">
                <BarList
                  items={data.top_agents.map<BarItem>((a) => ({
                    key: a.agent,
                    label: a.agent,
                    sublabel: `${a.chats} chat${a.chats === 1 ? '' : 's'}`,
                    value: a.messages,
                  }))}
                  valueLabel={(v) => `${formatNumber(v)} msgs`}
                  emptyText="No agent data."
                  activeKey={barFilter?.col === 'agents' ? barFilter.value : null}
                  onItemClick={(item) => handleBarClick('agents', item.key)}
                />
              </div>
            </Card>
            <Card title="Tool usage" subtitle="Most invoked tools — click to filter the conversations">
              <div className="max-h-[200px] overflow-y-auto">
                <BarList
                  items={data.top_tools.map<BarItem>((t) => ({ key: t.tool_name, label: t.tool_name, value: t.uses }))}
                  valueLabel={(v) => `${formatNumber(v)} uses`}
                  emptyText="No tool data."
                  activeKey={barFilter?.col === 'tools' ? barFilter.value : null}
                  onItemClick={(item) => handleBarClick('tools', item.key)}
                />
              </div>
            </Card>
          </div>

          <Card
            title="Conversations"
            subtitle={
              canReadMessages
                ? `${data.top_chats.length.toLocaleString()} conversation(s) in this period — click one to read it`
                : `${data.top_chats.length.toLocaleString()} conversation(s) in this period`
            }
            action={
              canReadMessages ? undefined : (
                <span
                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
                  title="Reading or exporting messages needs the ReadAnalyticsConversation right"
                >
                  <Lock size={12} aria-hidden />
                  Metadata only
                </span>
              )
            }
          >
            <ConversationsTable
              rows={data.top_chats}
              formatDateTime={formatInZone}
              onRowClick={canReadMessages ? (id) => setOpenId(id) : undefined}
              onUserClick={pickByEmail}
              canPickUser={canPickUser}
              externalFilter={barFilter ? { col: barFilter.col, values: [barFilter.value] } : null}
              onExternalFilterClear={() => setBarFilter(null)}
            />
          </Card>
        </>
      )}
    </div>
  );
}
