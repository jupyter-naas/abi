import './account-components.css';

type AccountPageHeaderProps = {
  title: string;
  subtitle: string;
  actions?: React.ReactNode;
  /** Before the title, e.g. a back button. */
  leading?: React.ReactNode;
};

export function AccountPageHeader({ title, subtitle, actions, leading }: AccountPageHeaderProps) {
  const text = (
    <div className="account-page-header-text">
      <h2 className="account-page-header-title">{title}</h2>
      <p className="account-page-header-subtitle">{subtitle}</p>
    </div>
  );
  return (
    <div
      className={
        actions
          ? 'account-page-header account-page-header-with-actions'
          : 'account-page-header'
      }
    >
      {leading ? (
        <div className="flex min-w-0 items-start gap-3">
          {leading}
          {text}
        </div>
      ) : (
        text
      )}
      {actions}
    </div>
  );
}
