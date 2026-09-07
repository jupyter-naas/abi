import type { LucideIcon } from 'lucide-react';
import './account-components.css';

type AccountActionRowProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  action: React.ReactNode;
};

export function AccountActionRow({
  icon: Icon,
  title,
  description,
  action,
}: AccountActionRowProps) {
  return (
    <div className="account-action-row">
      <div className="account-action-row-start">
        <div className="account-action-row-icon-wrap">
          <Icon size={20} />
        </div>
        <div>
          <h3 className="account-action-row-title">{title}</h3>
          <p className="account-action-row-description">{description}</p>
        </div>
      </div>
      <div className="account-action-row-action">{action}</div>
    </div>
  );
}
