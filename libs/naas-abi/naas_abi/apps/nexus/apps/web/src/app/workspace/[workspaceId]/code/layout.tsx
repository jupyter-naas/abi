import { Header } from '@/components/shell/header';

// The Code sub-app navigation (Workspaces / Branches / Pull requests + repo
// selector) lives in the left section panel (see code-section.tsx), like the
// Knowledge Graph section. We still render the shared top Header so the API
// status indicator, user menu and global controls stay visible — consistent
// with every other section. Each page renders its own toolbar below it.
export default function CodeLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <Header title="Code" />
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}
