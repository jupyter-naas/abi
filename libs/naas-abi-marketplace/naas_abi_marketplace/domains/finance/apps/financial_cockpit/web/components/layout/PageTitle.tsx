type PageTitleProps = {
  children: React.ReactNode;
  className?: string;
  hint?: string;
};

export function PageTitle({ children, className = '', hint }: PageTitleProps) {
  return (
    <div
      className={`page-title flex w-full min-w-0 items-center gap-3 sm:gap-4 mb-2 ${className}`.trim()}
    >
      <span className="page-title-rule" aria-hidden />
      <h2
        className={`type-title-3 m-0 min-w-0 shrink text-center leading-snug break-words${hint ? ' cursor-help' : ''}`}
        title={hint}
      >
        {children}
      </h2>
      <span className="page-title-rule" aria-hidden />
    </div>
  );
}
