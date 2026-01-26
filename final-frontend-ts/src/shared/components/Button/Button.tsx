import React from 'react';
import { useTheme } from '@/shared/contexts/ThemeContext';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
  variant?: 'primary' | 'secondary' | 'outline';
  fullWidth?: boolean;
  disabled?: boolean;
}

const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  fullWidth = false,
  disabled = false,
}) => {
  const { colors } = useTheme();

  const getBackgroundColor = () => {
    if (disabled) return colors.border;
    switch (variant) {
      case 'primary':
        return colors.primary;
      case 'secondary':
        return colors.secondary;
      case 'outline':
        return 'transparent';
      default:
        return colors.primary;
    }
  };

  const getTextColor = () => {
    if (disabled) return colors.textSecondary;
    return variant === 'outline' ? colors.primary : '#FFFFFF';
  };

  const getBorder = () => {
    return variant === 'outline' ? `2px solid ${colors.primary}` : 'none';
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        backgroundColor: getBackgroundColor(),
        color: getTextColor(),
        border: getBorder(),
        padding: '1rem 2rem',
        borderRadius: '0.75rem',
        fontSize: '1.125rem',
        fontWeight: '600',
        cursor: disabled ? 'not-allowed' : 'pointer',
        width: fullWidth ? '100%' : 'auto',
        transition: 'all 0.3s ease',
        opacity: disabled ? 0.6 : 1,
        minHeight: '3.25rem',
        lineHeight: '1.4',
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.backgroundColor =
            variant === 'primary'
              ? colors.primaryHover
              : variant === 'outline'
              ? colors.inputBg
              : colors.secondary;
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.backgroundColor = getBackgroundColor();
        }
      }}
    >
      {children}
    </button>
  );
};

export default Button;
