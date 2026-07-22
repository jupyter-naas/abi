type TopBarTitleProps = {
  children: React.ReactNode;
  className?: string;
};

export function TopBarTitle({ children, className = '' }: TopBarTitleProps) {
  return (
    <h1
      className={`type-title-3 m-0 min-w-0 text-center leading-snug break-words ${className}`.trim()}
    >
      {children}
    </h1>
  );
}
