import { describeDependency, type Dependency } from './graph-model';
export type LinkHover = { edge: Dependency; x: number; y: number } | null;
export function LinkTooltip({ hover }: { hover: LinkHover }) {
  if (!hover) return null;
  const description = describeDependency(hover.edge);
  return <div className="infrastructure-link-tooltip" role="tooltip" style={{ left: hover.x, top: hover.y }}><strong>{description.title}</strong><span>{description.detail}</span><small>{hover.edge.count} extracted relationships</small></div>;
}
