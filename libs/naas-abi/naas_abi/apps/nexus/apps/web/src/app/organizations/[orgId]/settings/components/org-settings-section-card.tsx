import './org-settings-components.css';

type OrgSettingsSectionCardProps = {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
  stack?: boolean;
  flush?: boolean;
  overflowHidden?: boolean;
};

function buildClassName({
  className,
  padded,
  stack,
  flush,
  overflowHidden,
}: Omit<OrgSettingsSectionCardProps, 'children'>) {
  const classes = ['org-settings-section-card'];
  if (padded) classes.push('org-settings-section-card-padded');
  if (stack) classes.push('org-settings-section-card-stack');
  if (flush) classes.push('org-settings-section-card-flush');
  if (overflowHidden) classes.push('org-settings-section-card-overflow-hidden');
  if (className) classes.push(className);
  return classes.join(' ');
}

export function OrgSettingsSectionCard({
  children,
  className,
  padded = false,
  stack = false,
  flush = false,
  overflowHidden = false,
}: OrgSettingsSectionCardProps) {
  return (
    <div
      className={buildClassName({
        className,
        padded,
        stack,
        flush,
        overflowHidden,
      })}
    >
      {children}
    </div>
  );
}
