import React, { useState } from 'react';
import { AiOutlineEye, AiOutlineEyeInvisible } from 'react-icons/ai';
import { useTheme } from '@/shared/contexts/ThemeContext';

interface InputProps {
  label?: string;
  type?: string;
  placeholder?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  required?: boolean;
  disabled?: boolean;
  showPasswordToggle?: boolean;
  actionButton?: {
    label: string;
    onClick: () => void;
  };
}

const Input: React.FC<InputProps> = ({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  required = false,
  disabled = false,
  showPasswordToggle = false,
  actionButton,
}) => {
  const { colors } = useTheme();
  const [showPassword, setShowPassword] = useState(false);
  const inputType = showPasswordToggle ? (showPassword ? 'text' : 'password') : type;

  return (
    <div style={{ marginBottom: '1.25rem' }}>
      {label && (
        <label
          style={{
            display: 'block',
            marginBottom: '0.5rem',
            color: colors.textPrimary,
            fontSize: '1rem',
            fontWeight: '600',
            lineHeight: '1.4',
          }}
        >
          {label}
        </label>
      )}
      <div style={{ position: 'relative', display: 'flex', gap: '0.75rem' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            type={inputType}
            placeholder={placeholder}
            value={value}
            onChange={onChange}
            required={required}
            disabled={disabled}
            style={{
              width: '100%',
              padding: '0.875rem 1.25rem',
              paddingRight: showPasswordToggle ? '3rem' : '1.25rem',
              borderRadius: '0.75rem',
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.inputBg,
              fontSize: '1.125rem',
              color: colors.textPrimary,
              outline: 'none',
              transition: 'border-color 0.3s ease',
              boxSizing: 'border-box',
              minHeight: '3.25rem',
              lineHeight: '1.4',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = colors.primary;
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = colors.border;
            }}
          />
          {showPasswordToggle && (
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              style={{
                position: 'absolute',
                right: '0.75rem',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '1.25rem',
                color: colors.textSecondary,
                padding: '0.25rem',
              }}
            >
              {showPassword ? <AiOutlineEye size={20} /> : <AiOutlineEyeInvisible size={20} />}
            </button>
          )}
        </div>
        {actionButton && (
          <button
            type="button"
            onClick={actionButton.onClick}
            style={{
              padding: '0.875rem 1.5rem',
              borderRadius: '0.75rem',
              border: 'none',
              backgroundColor: '#FCD34D',
              color: '#FFFFFF',
              fontSize: '1.125rem',
              fontWeight: '600',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              minHeight: '3.25rem',
            }}
          >
            {actionButton.label}
          </button>
        )}
      </div>
    </div>
  );
};

export default Input;
