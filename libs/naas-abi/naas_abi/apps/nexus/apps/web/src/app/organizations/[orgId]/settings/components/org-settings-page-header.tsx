import './org-settings-components.css';

type OrgSettingsPageHeaderProps = {
  title: string;
  subtitle: string;
  /** Shown next to the title, e.g. "4 users". */
  badge?: React.ReactNode;
  actions?: React.ReactNode;
};

export function OrgSettingsPageHeader({
  title,
  subtitle,
  badge,
  actions,
}: OrgSettingsPageHeaderProps) {
  return (
    <div
      className={
        actions
          ? 'org-settings-page-header org-settings-page-header-with-actions'
          : 'org-settings-page-header'
      }
    >
      <div className="org-settings-page-header-text">
        <div className="flex items-center gap-2">
          <h2 className="org-settings-page-header-title">{title}</h2>
          {badge !== undefined && badge !== null ? (
            <span className="inline-flex items-center bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {badge}
            </span>
          ) : null}
        </div>
        <p className="org-settings-page-header-subtitle">{subtitle}</p>
      </div>
      {actions}
    </div>
  );
}
