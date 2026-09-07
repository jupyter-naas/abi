import './account-components.css';

type AccountToggleProps = {
  checked: boolean;
  onChange: () => void;
  'aria-label'?: string;
};

export function AccountToggle({
  checked,
  onChange,
  'aria-label': ariaLabel,
}: AccountToggleProps) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      aria-label={ariaLabel}
      onClick={onChange}
      className={
        checked
          ? 'account-toggle account-toggle-on'
          : 'account-toggle account-toggle-off'
      }
    >
      <span className="account-toggle-knob" />
    </button>
  );
}
