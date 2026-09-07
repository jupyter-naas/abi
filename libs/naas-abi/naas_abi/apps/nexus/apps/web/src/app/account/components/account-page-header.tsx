import './account-components.css';

type AccountPageHeaderProps = {
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
};

export function AccountPageHeader({ title, subtitle, actions }: AccountPageHeaderProps) {
  return (
    <div
      className={
        actions
          ? 'account-page-header account-page-header-with-actions'
          : 'account-page-header'
      }
    >
      <div className="account-page-header-text">
        <h2 className="account-page-header-title">{title}</h2>
        <p className="account-page-header-subtitle">{subtitle}</p>
      </div>
      {actions}
    </div>
  );
}
