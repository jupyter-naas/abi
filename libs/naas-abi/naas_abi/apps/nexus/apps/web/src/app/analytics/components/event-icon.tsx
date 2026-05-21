'use client';

import {
  AlertCircle,
  ArrowDownToLine,
  Eye,
  FileUp,
  LogIn,
  LogOut,
  MailPlus,
  MousePointerClick,
  Play,
  Pause,
  Pencil,
  Plus,
  Search,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EventName } from '../lib/types';

const META: Record<EventName, { icon: LucideIcon; color: string; bg: string }> = {
  session_started: { icon: Play, color: 'text-emerald-600', bg: 'bg-emerald-500/10' },
  session_ended: { icon: Pause, color: 'text-slate-600', bg: 'bg-slate-500/10' },
  page_viewed: { icon: Eye, color: 'text-blue-600', bg: 'bg-blue-500/10' },
  workspace_opened: { icon: Eye, color: 'text-indigo-600', bg: 'bg-indigo-500/10' },
  workspace_created: { icon: Plus, color: 'text-emerald-600', bg: 'bg-emerald-500/10' },
  workspace_updated: { icon: Pencil, color: 'text-amber-600', bg: 'bg-amber-500/10' },
  file_uploaded: { icon: FileUp, color: 'text-violet-600', bg: 'bg-violet-500/10' },
  button_clicked: { icon: MousePointerClick, color: 'text-slate-600', bg: 'bg-slate-500/10' },
  search_performed: { icon: Search, color: 'text-sky-600', bg: 'bg-sky-500/10' },
  export_clicked: { icon: ArrowDownToLine, color: 'text-teal-600', bg: 'bg-teal-500/10' },
  invite_sent: { icon: MailPlus, color: 'text-pink-600', bg: 'bg-pink-500/10' },
  login: { icon: LogIn, color: 'text-emerald-600', bg: 'bg-emerald-500/10' },
  logout: { icon: LogOut, color: 'text-slate-600', bg: 'bg-slate-500/10' },
  error_seen: { icon: AlertCircle, color: 'text-rose-600', bg: 'bg-rose-500/10' },
};

export function EventIcon({ name, size = 14 }: { name: EventName; size?: number }) {
  const m = META[name];
  const Icon = m.icon;
  return (
    <span
      className={cn('inline-flex items-center justify-center', m.bg, m.color)}
      style={{ width: size + 12, height: size + 12 }}
    >
      <Icon size={size} />
    </span>
  );
}

export function formatEventName(name: EventName): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
