import { Header } from '@/components/shell/header';
import { ProjectPage } from '@/components/projects/project-page';

interface ProjectWorkspacePageProps {
  params: {
    workspaceId: string;
    segments: string[];
  };
}

export default function ProjectWorkspacePage({ params }: ProjectWorkspacePageProps) {
  const modulePath = params.segments.join('.');
  return (
    <div className="flex h-full flex-col">
      <Header title="Projects" />
      <ProjectPage modulePath={modulePath} />
    </div>
  );
}
