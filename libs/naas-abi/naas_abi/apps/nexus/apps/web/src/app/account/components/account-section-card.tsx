import './account-components.css';

type AccountSectionCardProps = {
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
}: Omit<AccountSectionCardProps, 'children'>) {
  const classes = ['account-section-card'];
  if (padded) classes.push('account-section-card-padded');
  if (stack) classes.push('account-section-card-stack');
  if (flush) classes.push('account-section-card-flush');
  if (overflowHidden) classes.push('account-section-card-overflow-hidden');
  if (className) classes.push(className);
  return classes.join(' ');
}

export function AccountSectionCard({
  children,
  className,
  padded = false,
  stack = false,
  flush = false,
  overflowHidden = false,
}: AccountSectionCardProps) {
  return (
    <div
      className={buildClassName({ className, padded, stack, flush, overflowHidden })}
    >
      {children}
    </div>
  );
}
