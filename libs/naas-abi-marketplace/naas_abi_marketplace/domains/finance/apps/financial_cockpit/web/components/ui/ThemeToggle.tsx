import { Button } from '@/components/ui/Button';

type ThemeToggleProps = {
  theme: 'light' | 'dark';
  onPress: () => void;
  className?: string;
};

function SunIcon() {
  return (
    <svg
      className="w-5 h-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      className="w-5 h-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3a6.5 6.5 0 1 0 11.5 11.5z" />
    </svg>
  );
}

export function ThemeToggle({ theme, onPress, className = '' }: ThemeToggleProps) {
  const isLight = theme === 'light';

  return (
    <Button
      variant="ghost"
      onPress={onPress}
      aria-label={isLight ? 'Activer le mode sombre' : 'Activer le mode clair'}
      className={`!w-auto min-h-11 min-w-11 justify-center px-3 ${className}`.trim()}
    >
      {isLight ? <MoonIcon /> : <SunIcon />}
    </Button>
  );
}
