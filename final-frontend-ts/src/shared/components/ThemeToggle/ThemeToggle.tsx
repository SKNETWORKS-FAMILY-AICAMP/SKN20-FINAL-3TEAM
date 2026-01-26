import React from 'react';
import { BsMoon, BsSun } from 'react-icons/bs';
import { useTheme } from '@/shared/contexts/ThemeContext';

interface ThemeToggleProps {
  style?: React.CSSProperties;
}

const ThemeToggle: React.FC<ThemeToggleProps> = ({ style }) => {
  const { theme, toggleTheme, colors } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      style={{
        background: 'none',
        border: `1px solid ${colors.border}`,
        borderRadius: '50%',
        width: '2rem',
        height: '2rem',
        fontSize: '1rem',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.3s ease',
        backgroundColor: colors.inputBg,
        ...style,
      }}
      title={theme === 'light' ? '다크 모드로 전환' : '라이트 모드로 전환'}
    >
      {theme === 'light' ? <BsMoon size={14} /> : <BsSun size={14} />}
    </button>
  );
};

export default ThemeToggle;
