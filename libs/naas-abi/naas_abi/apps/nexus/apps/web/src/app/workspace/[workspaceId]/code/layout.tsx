// The Code sub-app navigation (Workspaces / Branches / Pull requests + repo
// selector) lives in the left section panel (see code-section.tsx), like the
// Knowledge Graph section — so the layout is just a full-height passthrough.
export default function CodeLayout({ children }: { children: React.ReactNode }) {
  return <div className="h-full">{children}</div>;
}
