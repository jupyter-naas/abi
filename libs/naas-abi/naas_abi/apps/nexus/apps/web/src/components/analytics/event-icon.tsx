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
  Circle,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EventName } from './types';

const NEUTRAL = 'bg-muted text-muted-foreground';
const MARKED = 'bg-primary/10 text-primary';
const ALERT = 'bg-destructive/10 text-destructive';

/** One icon per event; colour only marks starts (primary) and errors (destructive), the
 *  name always says which event it is. */
const META: Record<EventName, { icon: LucideIcon; tone: string }> = {
  session_started: { icon: Play, tone: MARKED },
  session_ended: { icon: Pause, tone: NEUTRAL },
  page_viewed: { icon: Eye, tone: NEUTRAL },
  workspace_opened: { icon: Eye, tone: NEUTRAL },
  workspace_created: { icon: Plus, tone: MARKED },
  workspace_updated: { icon: Pencil, tone: NEUTRAL },
  file_uploaded: { icon: FileUp, tone: NEUTRAL },
  button_clicked: { icon: MousePointerClick, tone: NEUTRAL },
  search_performed: { icon: Search, tone: NEUTRAL },
  export_clicked: { icon: ArrowDownToLine, tone: NEUTRAL },
  invite_sent: { icon: MailPlus, tone: NEUTRAL },
  login: { icon: LogIn, tone: MARKED },
  logout: { icon: LogOut, tone: NEUTRAL },
  error_seen: { icon: AlertCircle, tone: ALERT },
};

const UNKNOWN = { icon: Circle, tone: NEUTRAL };

export function EventIcon({ name, size = 14 }: { name: EventName; size?: number }) {
  const m = META[name] ?? UNKNOWN;
  const Icon = m.icon;
  return (
    <span
      aria-hidden
      className={cn('inline-flex flex-shrink-0 items-center justify-center', m.tone)}
      style={{ width: size + 12, height: size + 12 }}
    >
      <Icon size={size} />
    </span>
  );
}

export function formatEventName(name: EventName): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
