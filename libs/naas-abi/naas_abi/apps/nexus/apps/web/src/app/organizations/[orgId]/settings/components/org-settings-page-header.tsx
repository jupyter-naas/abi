import './org-settings-components.css';

type OrgSettingsPageHeaderProps = {
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
};

export function OrgSettingsPageHeader({
  title,
  subtitle,
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
        <h2 className="org-settings-page-header-title">{title}</h2>
        <p className="org-settings-page-header-subtitle">{subtitle}</p>
      </div>
      {actions}
    </div>
  );
}
