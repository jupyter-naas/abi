import {
  FieldError,
  Input,
  Label,
  TextField as RACTextField,
  type TextFieldProps,
} from 'react-aria-components';

import { fieldInput, fieldLabel } from '@/lib/ariaStyles';

type AppTextFieldProps = TextFieldProps & {
  label: string;
  placeholder?: string;
  type?: 'text' | 'password';
  autoComplete?: string;
  className?: string;
};

export function TextField({
  label,
  placeholder,
  type = 'text',
  autoComplete,
  className = '',
  ...props
}: AppTextFieldProps) {
  return (
    <RACTextField {...props} className={`flex flex-col ${className}`.trim()}>
      <Label className={fieldLabel}>{label}</Label>
      <Input
        type={type}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className={fieldInput}
      />
      <FieldError className="text-red-500 text-xs mt-1" />
    </RACTextField>
  );
}
