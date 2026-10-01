import {
  AppWindow, BookOpen, Bot, Briefcase, Building2, Database, FileText, Folder, Globe, GraduationCap, Landmark,
  MapPin, MessageSquare, Network, Package, Presentation, Search, Sheet, Tag, Users, type LucideIcon,
} from 'lucide-react';

/** Icons a topic may name in its `icon` setting (lucide names). */
export const TOPIC_ICONS: Record<string, LucideIcon> = {
  Users, Building2, Briefcase, GraduationCap, MapPin, Package, FileText, BookOpen, Landmark, Tag, Globe, Search,
};

/** Topic icons plus the ones feature scopes use. */
const SCOPE_ICONS: Record<string, LucideIcon> = {
  ...TOPIC_ICONS, AppWindow, MessageSquare, Folder, Presentation, Sheet, Database, Network, Bot,
};

export function TopicIcon({ name, size = 14, className }: { name: string; size?: number; className?: string }) {
  const Icon = SCOPE_ICONS[name] || Search;
  return <Icon size={size} className={className} />;
}
