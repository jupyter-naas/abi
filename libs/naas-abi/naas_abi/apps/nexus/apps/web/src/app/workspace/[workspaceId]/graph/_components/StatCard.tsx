'use client';

export interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ElementType;
}

export function StatCard({ title, value, icon: Icon }: StatCardProps) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 flex items-center gap-2 text-muted-foreground">
        <Icon size={16} />
        <span className="text-sm">{title}</span>
      </div>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}
